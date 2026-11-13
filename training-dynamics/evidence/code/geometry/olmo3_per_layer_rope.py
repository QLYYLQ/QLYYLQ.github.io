#!/usr/bin/env python3
"""Isolated backport of Transformers PR #46911 OLMo3 per-layer RoPE.

This module is imported explicitly before constructing an OLMo3 model. It does
not run through sitecustomize and does not change any files in Transformers.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
from typing import Any
from pathlib import Path

import torch
import torch.nn as nn


PATCH_SCHEMA = "olmo3_per_layer_rope_backport_v1"
UPSTREAM_MERGE_COMMIT = "326683dc4d28355f534681c81681734328371f46"
UPSTREAM_PR_HEAD = "12b9e1d6c7d4f77b1b7191cf7a715acbdcf3a3b5"
UPSTREAM_CORE_COMMITS = ("5989c48", "f2a7a64", "20b842d")
UPSTREAM_FILES = {
    "configuration_olmo3.py": "350402470a9cfcd85db984694b0a0f26725fc1d41c4ecfd61274b370aa6fed3c",
    "modeling_olmo3.py": "ce6a099e66e6f84653ad630c509b810476f55fa851268e9f6d6e300938f2dd02",
    "modular_olmo3.py": "527963a4f46145752ec6baf4a947365d0d74bff66a7119f27ad4a9854a1be040",
}
REVIEWED_INSTALLED_SOURCES = {
    "5.5.4": {
        "modeling_olmo3.py": "a64b6ed0cae805e94facc64ae25de1bf80588acf2a74695c587f014cbe4a9a50",
        "configuration_olmo3.py": "65d1fa3673a5d1b4384134bee42374e99b2165fcce25934c33bbd5a9eadaa804",
    },
}


def _source_sha(value: Any) -> str:
    return hashlib.sha256(inspect.getsource(value).encode()).hexdigest()


def _nested_rope_parameters(flat: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if set(flat) >= {"sliding_attention", "full_attention"}:
        return copy.deepcopy(flat)
    full = copy.deepcopy(flat)
    theta = full.get("rope_theta")
    if theta is None:
        raise ValueError("flat OLMo3 rope parameters are missing rope_theta")
    return {
        "sliding_attention": {"rope_type": "default", "rope_theta": theta},
        "full_attention": full,
    }


def _position_embeddings_fp32(rotary, x, position_ids, maybe_autocast):
    """Official #46911/follow-up behavior: compute and return cos/sin in FP32."""
    import torch

    inv_freq_expanded = rotary.inv_freq[None, :, None].float().expand(position_ids.shape[0], -1, 1).to(x.device)
    position_ids_expanded = position_ids[:, None, :].float()
    device_type = x.device.type if isinstance(x.device.type, str) else "cpu"
    with maybe_autocast(device_type=device_type, enabled=False):
        freqs = (inv_freq_expanded.float() @ position_ids_expanded.float()).transpose(1, 2)
        emb = torch.cat((freqs, freqs), dim=-1)
        cos = emb.cos() * rotary.attention_scaling
        sin = emb.sin() * rotary.attention_scaling
    return cos, sin


class PerLayerRotaryContainer(nn.Module):
    """Two installed rotary modules with lossless FP32 buffer restoration."""

    def __init__(self, rotaries: dict[str, nn.Module], maybe_autocast, effective_rope_parameters):
        super().__init__()
        self.rotaries = nn.ModuleDict(rotaries)
        self.maybe_autocast = maybe_autocast
        self.effective_rope_parameters = copy.deepcopy(effective_rope_parameters)
        # Plain CPU tensors are deliberately not registered as buffers, so an
        # actor-wide .to(bfloat16) cannot destroy their FP32 values.
        self._canonical_inv_freq_cpu = {
            name: rotary.inv_freq.detach().float().cpu().clone() for name, rotary in self.rotaries.items()
        }
        self._canonical_original_inv_freq_cpu = {
            name: rotary.original_inv_freq.detach().float().cpu().clone()
            for name, rotary in self.rotaries.items()
            if hasattr(rotary, "original_inv_freq")
        }

    def _apply(self, fn, recurse=True):
        super()._apply(fn, recurse=recurse)
        # Restore from the never-cast CPU canonical copy. Calling .float() on
        # a BF16-rounded buffer would not recover the lost mantissa bits.
        for name, rotary in self.rotaries.items():
            rotary.inv_freq = self._canonical_inv_freq_cpu[name].to(rotary.inv_freq.device)
            if name in self._canonical_original_inv_freq_cpu:
                rotary.original_inv_freq = self._canonical_original_inv_freq_cpu[name].to(
                    rotary.original_inv_freq.device
                )
        return self

    def forward(self, x, position_ids, layer_type: str):
        return _position_embeddings_fp32(self.rotaries[layer_type], x, position_ids, self.maybe_autocast)

    def fp32_invariant(self) -> bool:
        return all(rotary.inv_freq.dtype == torch.float32 for rotary in self.rotaries.values())


def build_per_layer_rotary_container(config, modeling_module):
    """Build the reviewed container without constructing a full model."""
    nested = _nested_rope_parameters(config.rope_parameters)
    rotaries = {}
    # `from_pretrained(low_cpu_mem_usage=True)` constructs the model under a
    # meta-device context. These modules have no parameters and only tiny
    # non-persistent rotary buffers, so explicitly materialize them on CPU;
    # otherwise a canonical FP32 copy cannot be recovered from meta tensors.
    with torch.device("cpu"):
        for layer_type in sorted(set(config.layer_types)):
            layer_config = copy.deepcopy(config)
            layer_config.rope_parameters = copy.deepcopy(nested[layer_type])
            rotaries[layer_type] = modeling_module.Olmo3RotaryEmbedding(config=layer_config)
    return PerLayerRotaryContainer(rotaries, modeling_module.maybe_autocast, nested), nested


def install_patch() -> dict[str, Any]:
    """Install the isolated class patch and return its provenance receipt."""
    import transformers
    from transformers.models.olmo3 import modeling_olmo3 as m

    reviewed = REVIEWED_INSTALLED_SOURCES.get(transformers.__version__)
    if reviewed is None:
        raise RuntimeError(
            f"{PATCH_SCHEMA} has no reviewed source pin for Transformers {transformers.__version__}; "
            "refuse to patch an unknown minor/source"
        )
    installed_modeling_sha = hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
    from transformers.models.olmo3 import configuration_olmo3 as c

    installed_configuration_sha = hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest()
    if installed_modeling_sha != reviewed["modeling_olmo3.py"]:
        raise RuntimeError(f"installed modeling_olmo3.py SHA drift: {installed_modeling_sha}")
    if installed_configuration_sha != reviewed["configuration_olmo3.py"]:
        raise RuntimeError(f"installed configuration_olmo3.py SHA drift: {installed_configuration_sha}")

    if getattr(m.Olmo3Model, "_continuation_per_layer_rope_patch", False):
        return dict(m.Olmo3Model._continuation_per_layer_rope_receipt)

    original_init = m.Olmo3Model.__init__
    original_forward = m.Olmo3Model.forward
    original_init_sha = _source_sha(original_init)
    original_forward_sha = _source_sha(original_forward)

    def patched_init(self, config):
        original_init(self, config)
        if set(config.rope_parameters) >= {"sliding_attention", "full_attention"}:
            raise RuntimeError("native nested OLMo3 RoPE detected; this backport must not be applied")
        self.rotary_emb_by_layer_type, nested = build_per_layer_rotary_container(config, m)
        # The old global rotary was created under the outer meta context and
        # is no longer used. Remove it from the module tree so a later
        # `.to(device)` cannot try to copy an unmaterialized meta buffer.
        self.rotary_emb = nn.Identity()
        # Keep the public config flat. Native vLLM 0.18/0.22 expects that
        # schema when reloading a saved checkpoint. The effective per-layer
        # schedule lives only on the private runtime container and receipt.
        self._continuation_per_layer_rope_active = True

    def patched_forward(
        self,
        input_ids=None,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        inputs_embeds=None,
        use_cache=None,
        **kwargs,
    ):
        if (input_ids is None) ^ (inputs_embeds is not None):
            raise ValueError("You must specify exactly one of input_ids or inputs_embeds")
        if inputs_embeds is None:
            inputs_embeds = self.embed_tokens(input_ids)
        if use_cache and past_key_values is None:
            past_key_values = m.DynamicCache(config=self.config)
        if position_ids is None:
            past_seen_tokens = past_key_values.get_seq_length() if past_key_values is not None else 0
            position_ids = torch.arange(inputs_embeds.shape[1], device=inputs_embeds.device) + past_seen_tokens
            position_ids = position_ids.unsqueeze(0)
        if not isinstance(causal_mask_mapping := attention_mask, dict):
            mask_kwargs = {
                "config": self.config,
                "inputs_embeds": inputs_embeds,
                "attention_mask": attention_mask,
                "past_key_values": past_key_values,
                "position_ids": position_ids,
            }
            causal_mask_mapping = {
                "full_attention": m.create_causal_mask(**mask_kwargs),
                "sliding_attention": m.create_sliding_window_causal_mask(**mask_kwargs),
            }
        hidden_states = inputs_embeds
        position_embeddings = {
            layer_type: self.rotary_emb_by_layer_type(hidden_states, position_ids, layer_type)
            for layer_type in set(self.config.layer_types)
        }
        for decoder_layer in self.layers[: self.config.num_hidden_layers]:
            layer_type = decoder_layer.self_attn.attention_type
            hidden_states = decoder_layer(
                hidden_states,
                attention_mask=causal_mask_mapping[layer_type],
                position_ids=position_ids,
                past_key_values=past_key_values,
                position_embeddings=position_embeddings[layer_type],
                **kwargs,
            )
        hidden_states = self.norm(hidden_states)
        return m.BaseModelOutputWithPast(last_hidden_state=hidden_states, past_key_values=past_key_values)

    patched_forward_impl_sha = _source_sha(patched_forward)
    # Preserve the two runtime decorators present on the installed 5.3/5.5
    # implementation. The upstream source change is otherwise the same loop:
    # compute position embeddings per layer type and route by attention type.
    patched_forward = m.capture_outputs(patched_forward)
    patched_forward = m.merge_with_config_defaults(patched_forward)
    m.Olmo3Model.__init__ = patched_init
    m.Olmo3Model.forward = patched_forward
    receipt = {
        "schema": PATCH_SCHEMA,
        "upstream_merge_commit": UPSTREAM_MERGE_COMMIT,
        "upstream_pr_head": UPSTREAM_PR_HEAD,
        "upstream_core_commits": list(UPSTREAM_CORE_COMMITS),
        "upstream_files": dict(UPSTREAM_FILES),
        "transformers_version": transformers.__version__,
        "installed_modeling_olmo3_sha256": installed_modeling_sha,
        "installed_configuration_olmo3_sha256": installed_configuration_sha,
        "installed_original_init_sha256": original_init_sha,
        "installed_original_forward_sha256": original_forward_sha,
        "patched_init_source_sha256": _source_sha(patched_init),
        "patched_forward_source_sha256": patched_forward_impl_sha,
        "semantics": "default unscaled RoPE for sliding_attention; configured scaled RoPE for full_attention",
        "config_mutation": "none: public flat config.rope_parameters is preserved; private container records sliding default/full YaRN; checkpoint weights are unchanged",
        "unused_global_rotary": "replaced by nn.Identity; zero parameters/state/buffers",
        "sitecustomize_modified": False,
    }
    m.Olmo3Model._continuation_per_layer_rope_patch = True
    m.Olmo3Model._continuation_per_layer_rope_receipt = dict(receipt)
    return receipt


__all__ = [
    "install_patch", "build_per_layer_rotary_container", "PerLayerRotaryContainer",
    "PATCH_SCHEMA", "UPSTREAM_MERGE_COMMIT", "UPSTREAM_FILES",
]
