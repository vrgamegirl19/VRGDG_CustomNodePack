"""CPU checks for the Builder-independent H3 chunked pass 2 and the studio templates."""
import ast
from contextlib import redirect_stdout
import importlib
import io
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import torch

PACK = Path(__file__).resolve().parents[1]
COMFY = next(path for path in PACK.parents if (path / "comfy").is_dir())
sys.path.insert(0, str(COMFY))
import comfy.cli_args
comfy.cli_args.args.cpu = True
package = types.ModuleType("standalone_h3_test")
package.__path__ = [str(PACK)]
sys.modules[package.__name__] = package
core = importlib.import_module(f"{package.__name__}.h3_standalone_pass2_core")
nodes = importlib.import_module(f"{package.__name__}.h3_standalone_pass2")


def latent_for(tokens):
    video = torch.arange(tokens, dtype=torch.float32).view(1, 1, -1, 1, 1).expand(1, 24, -1, 2, 2).clone()
    audio = torch.zeros(1, 32, 2, round(core.frame_at(tokens) * 40 / 24))
    return {"samples": core.NestedTensor((video, audio))}


class Upscaler:
    def upscale(self, latent, model, scale):
        return ({"samples": latent["samples"].repeat_interleave(2, -1).repeat_interleave(2, -2)},)


class Guider:
    def __init__(self, model):
        pass

    def set_conds(self, cond):
        pass


class StandaloneTests(unittest.TestCase):
    def run_sampler(self, namespace, mode="locked", upscale="per_window", budget=0):
        calls = []

        def sample(noise, guider, sampler, sigmas, piece):
            video, audio = core.av_parts(piece)
            mask, audio_mask = piece["noise_mask"].unbind()
            self.assertFalse(audio_mask.any())
            calls.append((noise.seed, video.clone(), mask.clone()))
            return ({"samples": core.NestedTensor((video + mask * len(calls), audio + 123))},)

        with redirect_stdout(io.StringIO()), patch.dict(namespace, Guider_Basic=Guider), patch.object(core.SamplerCustomAdvanced, "execute", side_effect=sample):
            result, report = namespace["run_chunks"](
                latent_for(102), None, [[None, {}]], {}, Upscaler(), None, torch.tensor([0.2, 0]),
                2.0, 3.0, 1.6, mode, 42, tail_trim_seconds=0.7,
                max_window_tokens=budget, upscale_mode=upscale)
        return result, calls, report

    def test_tail_trim_locked_history_and_exact_audio(self):
        result, calls, report = self.run_sampler(core.__dict__)
        video, audio = core.av_parts(result)
        self.assertEqual(core.window_plan(102, 3, 1.6, 0.7)[0], (0, 22, 17))
        self.assertEqual(len(calls), 9)
        self.assertEqual(calls[1][0], 52)
        self.assertTrue(torch.all(calls[1][2][:, :, :7] == 0))
        self.assertTrue(torch.all(calls[1][2][:, :, 7:] == 1))
        self.assertTrue(torch.equal(calls[1][1][:, :, :7], calls[0][1][:, :, 10:17] + 1))
        self.assertEqual(video.shape, (1, 24, 102, 4, 4))
        self.assertFalse(audio.any())
        self.assertEqual(video.device.type, "cpu")
        self.assertIn("tail trim 5 tokens", report)

    def test_matches_builder_algorithm_without_importing_builder(self):
        root = COMFY / "custom_nodes" / "comfyui-vrgamedevgirl" / "minimax"
        if not (root / "chunked_pass2.py").is_file():
            self.skipTest("Optional local Builder reference source is absent")
        namespace = dict(core.__dict__)
        for filename, names in (("chunk_plan.py", {"window_plan", "budget_window_tokens", "tokens_per_latent_frame"}),
                                ("chunked_pass2.py", {"join_chunk", "run_chunks"})):
            tree = ast.parse((root / filename).read_text())
            functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
            module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *functions], type_ignores=[])
            exec(compile(ast.fix_missing_locations(module), filename, "exec"), namespace)
        for mode in ("locked", "crossfade"):
            for upscale in ("per_window", "whole_clip"):
                for budget in (0, 100):
                    with self.subTest(mode=mode, upscale=upscale, budget=budget):
                        ours, ours_calls, _ = self.run_sampler(core.__dict__, mode, upscale, budget)
                        reference, reference_calls, _ = self.run_sampler(namespace, mode, upscale, budget)
                        for a, b in zip(ours["samples"].unbind(), reference["samples"].unbind()):
                            self.assertTrue(torch.equal(a, b))
                        self.assertEqual(len(ours_calls), len(reference_calls))
                        for a, b in zip(ours_calls, reference_calls):
                            self.assertEqual(a[0], b[0])
                            self.assertTrue(torch.equal(a[1], b[1]))
                            self.assertTrue(torch.equal(a[2], b[2]))

    def test_unload_passes_the_value_through_every_run(self):
        value = object()
        with patch.object(nodes.comfy.model_management, "unload_all_models") as unload, \
                patch.object(nodes.comfy.model_management, "soft_empty_cache"):
            self.assertIs(nodes.VRGDG_H3StandaloneUnloadModels().unload(value)[0], value)
        unload.assert_called_once()
        self.assertTrue(math.isnan(nodes.VRGDG_H3StandaloneUnloadModels.IS_CHANGED()))

    def test_backend_uses_registered_lbh_node_and_rejects_unknown_paths(self):
        class Backend:
            def run(self, *args):
                return args
        with patch.dict(nodes.nodes.NODE_CLASS_MAPPINGS, {"MinimaxH3LatentUpscalerNode3D": Backend}, clear=True):
            result = nodes._LearnedUpscaler().upscale({}, {"path": "checkpoint", "device": "cpu", "precision": "fp32"}, 2)
        self.assertEqual(result[1:], ("checkpoint", 2, "cpu", "fp32"))
        with patch.object(nodes.folder_paths, "get_filename_list", return_value=[]):
            with self.assertRaises(ValueError):
                nodes.VRGDG_H3StandalonePass2().sample({}, None, [], None, None, "../bad.pth", "cpu", "fp32", 2, 3, 1.6, "locked", 42, 0.7, 0, "per_window")

    def test_studio_templates_only_use_vrgdg_nodes_from_this_pack(self):
        audio = (PACK / "MiniMaxH3LongScene" / "audio_mode.py").read_text(encoding="utf-8")
        audio_nodes = {key.value for node in ast.parse(audio).body if isinstance(node, ast.Assign)
                       and getattr(node.targets[0], "id", "") == "NODE_CLASS_MAPPINGS" for key in node.value.keys}
        this_pack = set(nodes.NODE_CLASS_MAPPINGS) | audio_nodes
        for name in ("H3_Batched_RefToVideo_API.json", "H3_Batched_ImageToVideo_API.json"):
            prompt = json.loads((PACK / "workflows" / "api" / name).read_text(encoding="utf-8"))
            for node_id, node in prompt.items():
                if node["class_type"].startswith("VRGDG_"):
                    self.assertIn(node["class_type"], this_pack, f"{name} node {node_id}")
                for value in node["inputs"].values():
                    if isinstance(value, list):
                        self.assertIn(value[0], prompt, f"{name} node {node_id} links to a missing node")


if __name__ == "__main__":
    unittest.main()
