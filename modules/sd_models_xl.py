from __future__ import annotations

import torch

import sgm.models.diffusion
import sgm.modules.diffusionmodules.denoiser_scaling
import sgm.modules.diffusionmodules.discretizer
from modules import devices, shared, prompt_parser


def get_learned_conditioning(self: sgm.models.diffusion.DiffusionEngine, batch: prompt_parser.SdConditioning | list[str]):
    for embedder in self.conditioner.embedders:
        embedder.ucg_rate = 0.0

    width = getattr(self, 'target_width', 1024)
    height = getattr(self, 'target_height', 1024)

    sdxl_conds = {
        "txt": batch,
        "original_size_as_tuple": torch.tensor([height, width]).repeat(len(batch), 1).to(devices.device, devices.dtype),
        "crop_coords_top_left": torch.tensor([shared.opts.sdxl_crop_top, shared.opts.sdxl_crop_left]).repeat(len(batch), 1).to(devices.device, devices.dtype),
        "target_size_as_tuple": torch.tensor([height, width]).repeat(len(batch), 1).to(devices.device, devices.dtype),
    }

    force_zero_negative_prompt = getattr(batch, 'is_negative_prompt', False) and all(x == '' for x in batch)
    c = self.conditioner(sdxl_conds, force_zero_embeddings=['txt'] if force_zero_negative_prompt else [])

    return c


def apply_model(self: sgm.models.diffusion.DiffusionEngine, x, t, cond):
    return self.model(x, t, cond)


def get_first_stage_encoding(self, x):  # SDXL's encode_first_stage does everything so get_first_stage_encoding is just there for compatibility
    return x

def extend_sdxl(model):
    dtype = next(model.model.diffusion_model.parameters()).dtype
    model.model.diffusion_model.dtype = dtype
    model.model.conditioning_key = 'crossattn'

    model.cond_stage_model = [x for x in model.conditioner.embedders if 'CLIPEmbedder' in type(x).__name__][0]
    model.cond_stage_key = model.cond_stage_model.input_key

    model.parameterization = "v" if isinstance(model.denoiser.scaling, sgm.modules.diffusionmodules.denoiser_scaling.VScaling) else "eps"

    discretization = sgm.modules.diffusionmodules.discretizer.LegacyDDPMDiscretization()
    model.alphas_cumprod = torch.asarray(discretization.alphas_cumprod, device=devices.device, dtype=dtype)

    model.is_sdxl = True


sgm.models.diffusion.DiffusionEngine.get_learned_conditioning = get_learned_conditioning
sgm.models.diffusion.DiffusionEngine.apply_model = apply_model
sgm.models.diffusion.DiffusionEngine.get_first_stage_encoding = get_first_stage_encoding

sgm.modules.attention.print = lambda *args: None
sgm.modules.diffusionmodules.model.print = lambda *args: None
sgm.modules.diffusionmodules.openaimodel.print = lambda *args: None
sgm.modules.encoders.modules.print = lambda *args: None

# this gets the code to load the vanilla attention that we override
sgm.modules.attention.SDP_IS_AVAILABLE = True
sgm.modules.attention.XFORMERS_IS_AVAILABLE = False