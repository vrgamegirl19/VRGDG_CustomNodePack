"""Template filling for the VRGDG MiniMax studio."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

PACK = Path(__file__).resolve().parents[1]
COMFY = next(path for path in PACK.parents if (path / "comfy").is_dir())
sys.path.insert(0, str(COMFY))
package = types.ModuleType("minimax_studio_test")
package.__path__ = [str(PACK)]
sys.modules[package.__name__] = package
core = importlib.import_module(f"{package.__name__}.minimax_studio_core")

MODELS = {
    "diffusion_models": ["Minimax-h3_Singularity_ref2va_v2_int8.safetensors", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"],
    "text_encoders": ["qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"],
    "vae": ["minimax_h3_video_vae_fp16.safetensors", "minimax_h3_audio_vae_fp32.safetensors"],
    "loras": ["dmad_minimax_h3_4step_full_critic_comfyui.safetensors"],
    "latent_upscale_models": ["minimax_h3_latent_upscaler_3d_bf16.safetensors"],
}


def settings(mode, images=(), **extra):
    return {"mode": mode, "prompt": "A fennec-eared girl waves.", "images": list(images), "duration": 7,
            "width": 1088, "height": 1920, "seed": 5, **extra}


def links(prompt):
    """Every node a link points to exists."""
    for node in prompt.values():
        for value in node["inputs"].values():
            if isinstance(value, list):
                assert value[0] in prompt, value


@patch.object(core.folder_paths, "exists_annotated_filepath", lambda name: True)
@patch.object(core.folder_paths, "get_filename_list", lambda folder: MODELS[folder])
class MiniMaxStudioTests(unittest.TestCase):
    def test_text_to_video_drops_the_start_image(self):
        prompt = core.build_prompt(settings("text_to_video"))
        self.assertNotIn("301", prompt)
        self.assertNotIn("first_frame", prompt["136"]["inputs"])
        self.assertEqual(prompt["136"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertEqual(prompt["138"]["inputs"]["value"], "A fennec-eared girl waves.")
        self.assertEqual((prompt["115"]["inputs"]["value"], prompt["184"]["inputs"]["value"]), (1088, 1920))
        self.assertEqual((prompt["129"]["inputs"]["noise_seed"], prompt["9502"]["inputs"]["seed"]), (5, 5))
        self.assertEqual(prompt["132"]["inputs"]["value"], 7.0)
        links(prompt)

    def test_advanced_settings_reach_both_passes(self):
        advanced = {"chunk_seconds": 6, "overlap_seconds": 1.2, "tail_trim_seconds": 0.5, "pass1_steps": 6,
                    "pass2_denoise": 0.3, "pass2_steps": 4, "upscale_scale": 2, "crf": 17, "fp16_accumulation": False,
                    "ref_image_size": "max"}
        prompt = core.build_prompt(settings("text_to_video", duration=30, advanced=advanced))
        pass2 = prompt["9502"]["inputs"]
        self.assertEqual((pass2["chunk_seconds"], pass2["overlap_seconds"], pass2["tail_trim_seconds"]), (6.0, 1.2, 0.5))
        self.assertEqual((prompt["124"]["inputs"]["steps"], prompt["191"]["inputs"]["value"], prompt["190"]["inputs"]["value"]), (6, 0.3, 4))
        self.assertEqual((prompt["142"]["inputs"]["crf"], prompt["141"]["inputs"]["enable_fp16_accumulation"]), (17, False))
        self.assertIsInstance(prompt["185"]["inputs"]["value"], float)
        # ref_image_size only exists in the reference workflow
        self.assertNotIn("ref_image_size", prompt["136"]["inputs"])
        self.assertEqual(core.build_prompt(settings("reference_to_video", advanced=advanced))["136"]["inputs"]["ref_image_size"], "max")
        self.assertEqual(prompt["132"]["inputs"]["value"], 30.0)
        self.assertEqual(core.build_prompt(settings("text_to_video"))["9502"]["inputs"]["chunk_seconds"], 8)
        with self.assertRaises(ValueError):
            core.build_prompt(settings("text_to_video", advanced={"positive_prompt_node": 1}))

    def test_advanced_choices_come_from_the_installed_nodes(self):
        class Sampler:
            @classmethod
            def INPUT_TYPES(cls):
                return {"required": {"sampler_name": ("COMBO", {"options": ["lcm", "euler", "res_multistep"]})}}

        class Scheduler:
            @classmethod
            def INPUT_TYPES(cls):
                return {"required": {"scheduler": (["simple", "beta"],), "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                                     "denoise": ("FLOAT", {"min": 0.0, "max": 1.0, "step": 0.01})}}

        with patch.object(core.nodes, "NODE_CLASS_MAPPINGS", {"KSamplerSelect": Sampler, "BasicScheduler": Scheduler}):
            fields = {field["key"]: field for group in core.advanced_settings() for field in group["fields"]}
            self.assertEqual(fields["pass1_sampler"]["options"], ["lcm", "euler", "res_multistep"])
            self.assertEqual(fields["pass1_sampler"]["defaults"]["image_to_video"], "lcm")
            self.assertEqual(fields["pass1_scheduler"]["options"], ["simple", "beta"])
            self.assertEqual((fields["pass1_steps"]["kind"], fields["pass1_steps"]["min"]), ("INT", 1))
            self.assertIsNone(fields["ref_image_size"]["defaults"]["text_to_video"])
            self.assertEqual(fields["ref_image_size"]["defaults"]["reference_to_video"], "match")
            self.assertEqual(fields["crf"]["kind"], "INT")
            prompt = core.build_prompt(settings("image_to_video", ["a.png"], advanced={"pass2_sampler": "euler"}))
            self.assertEqual(prompt["210"]["inputs"]["sampler_name"], "euler")
            with self.assertRaises(ValueError):
                core.build_prompt(settings("image_to_video", ["a.png"], advanced={"pass2_sampler": "not_a_sampler"}))

    def test_image_to_video_loads_one_start_image(self):
        prompt = core.build_prompt(settings("image_to_video", ["start.png"]))
        self.assertEqual(prompt["301"]["inputs"]["image"], "start.png")
        self.assertEqual(prompt["136"]["inputs"]["first_frame"], ["301", 0])
        links(prompt)
        with self.assertRaises(ValueError):
            core.build_prompt(settings("image_to_video"))

    def test_reference_to_video_adds_one_loader_per_picture(self):
        names = [f"ref{i}.png" for i in range(4)]
        prompt = core.build_prompt(settings("reference_to_video", names))
        refs = {k: v for k, v in prompt["136"]["inputs"].items() if k.startswith("ref_images.")}
        self.assertEqual(refs, {f"ref_images.ref_image_{i}": [f"ref_image_{i}", 0] for i in range(4)})
        self.assertEqual([prompt[f"ref_image_{i}"]["inputs"]["image"] for i in range(4)], names)
        self.assertNotIn("301", prompt)
        self.assertNotIn("302", prompt)
        links(prompt)
        with self.assertRaises(ValueError):
            core.build_prompt(settings("reference_to_video", [f"{i}.png" for i in range(10)]))

    def test_models_are_checked_against_the_model_folders(self):
        prompt = core.build_prompt(settings("text_to_video", models={"diffusion_model": MODELS["diffusion_models"][0]}))
        self.assertEqual(prompt["141"]["inputs"]["model_name"], MODELS["diffusion_models"][0])
        with self.assertRaises(ValueError):
            core.build_prompt(settings("text_to_video", models={"diffusion_model": "../../secret.safetensors"}))

    def test_defaults_come_from_the_templates(self):
        defaults = core.model_defaults()
        self.assertEqual(defaults["reference_to_video"]["diffusion_model"], "Minimax-h3_Singularity_ref2va_v2_int8.safetensors")
        self.assertEqual(defaults["image_to_video"]["diffusion_model"], "minimax_h3_fl2va_pruned_int8_convrot.safetensors")

    def test_requirements_report_installed_files_and_links(self):
        installed = {"DiffusionModelLoaderKJ": 1, "MinimaxH3LatentUpscaler3D": 1, "MiniMaxH3ImageToVideo": 1,
                     "MiniMaxH3ReferenceToVideo": 1, "MiniMaxH3SigmaShift": 1, "ComfyMathExpression": 1}
        with patch.object(core.nodes, "NODE_CLASS_MAPPINGS", installed):
            report = core.requirements()
        packs = {pack["name"]: pack for pack in report["custom_nodes"]}
        self.assertTrue(packs["ComfyUI (latest)"]["installed"])
        self.assertTrue(packs["ComfyUI-KJNodes"]["installed"])
        self.assertFalse(packs["ComfyUI-VideoHelperSuite"]["installed"])
        self.assertNotIn("note", packs["ComfyUI-VideoHelperSuite"])
        upscaler_pack = packs["Comfyui_Minimax_h3_latent_Upscaler"]
        self.assertFalse(upscaler_pack["installed"])
        self.assertIn("Aug 28", upscaler_pack["note"])

        rows = {row["key"]: row for row in report["models"]["reference_to_video"]}
        video = rows["diffusion_model"]["options"]
        self.assertEqual(video[0]["installed_as"], "Minimax-h3_Singularity_ref2va_v2_int8.safetensors")
        self.assertIsNone(video[2]["installed_as"])
        self.assertTrue(all(option["url"].startswith("https://huggingface.co/") for row in rows.values() for option in row["options"]))
        # the older flat name of the LBH checkpoint counts as the same download
        self.assertEqual(rows["upscaler"]["options"][0]["installed_as"], "minimax_h3_latent_upscaler_3d_bf16.safetensors")
        self.assertEqual({row["key"]: row["options"][0]["file"] for row in report["models"]["image_to_video"]}["diffusion_model"],
                         "minimax_h3_fl2va_pruned_int8_convrot.safetensors")

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            core.build_prompt(settings("video_to_video"))


if __name__ == "__main__":
    unittest.main()
