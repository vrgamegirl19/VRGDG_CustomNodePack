"""MiniMaxH3LongScene nodes and the DMAD + Long Scenes workflow that uses them."""

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

try:
    import torch
except ModuleNotFoundError:
    torch = None


ROOT = Path(__file__).resolve().parents[1]
NODE_FOLDER = ROOT / "MiniMaxH3LongScene"
WORKFLOW = ROOT / "workflows" / "MiniMaxH3_DMAD_LongScene_2Pass.json"

# The Video Builder's DMAD preset and Long Scenes window values (comfyui-vrgamedevgirl minimax/settings_payload.py
# DMAD_PRESET and minimax/chunk_plan.py). The workflow is generated with them.
DMAD = {"pass1": ("lcm", "simple", 4, 1.0), "shift": (12.0, 2.0), "pass2": ("res_multistep", 3, 0.2),
        "dmad_lora": ("dmad_minimax_h3_4step_full_critic_comfyui.safetensors", 1.0),
        "refiner_lora": ("minimax_h3_open_regenerate_2k_refiner_rank_16_bf16.safetensors", 0.7)}
WINDOWS = {"chunk_seconds": 3.0, "overlap_seconds": 1.6, "overlap_mode": "locked", "tail_trim_seconds": 0.7,
           "upscale": "per_window"}
BUILDER_NODES = {"VRGDG_MiniMaxH3ChunkedPass2", "VRGDG_MiniMaxH3LatentUpscaleModelLoader"}


def load_module(name):
    """One file of MiniMaxH3LongScene without importing the rest of the pack."""
    spec = importlib.util.spec_from_file_location(f"long_scene_test_{name}", NODE_FOLDER / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHOT_PROMPT = (
    "detailed_description:\nLook.\n\n"
    "[Shot 1] A continuous medium close-up of <Subject 1>: <Subject 1> sings in sync with the vocals in <Audio 1> "
    "from 1.0 s to 4.44 s, <d>[English, soft singing] my brother's gone quiet</d>, delivered softly.\n\n"
    "[Shot 2] At 00:04.600, continuing directly from the previous shot's final moment, <Subject 1> sings in sync "
    "with the vocals in <Audio 1> from 4.76 s to 5.76 s, <d>[English, quiet] I breathe the air.</d>, delivered softly.\n\n"
    "overall_soundscape:\n<Audio 1> remains the sole complete soundtrack.\n"
)


class PromptTimingTests(unittest.TestCase):
    def setUp(self):
        self.strip = load_module("prompt_timing").strip_prompt_timing

    def test_lyric_cues_dialogue_and_times_are_gone(self):
        text = self.strip(SHOT_PROMPT)
        for fragment in ("<d>", "</d>", " s to ", "At 00:04.600", "brother"):
            self.assertNotIn(fragment, text, fragment)
        self.assertIn("sings in sync with the vocals in <Audio 1>, delivered softly", text)
        self.assertIn("[Shot 2] Continuing directly from the previous shot's final moment", text)
        self.assertTrue(text.endswith("overall_soundscape:\n<Audio 1> remains the sole complete soundtrack.\n"))

    def test_a_prompt_with_no_timing_is_unchanged(self):
        plain = "detailed_description:\n[Shot 1] A wide shot of the street at night.\n"
        self.assertEqual(self.strip(plain), plain)

    def test_shots_that_only_differed_by_lyric_and_time_are_merged(self):
        shot = ("[Shot {n}] At 00:0{n}.000, continuing directly, <Subject 1> sings in sync with the vocals in "
                "<Audio 1> from {n}.0 s to {m}.0 s, <d>[tag] line {n}</d>, delivered softly.")
        prompt = "\n\n".join(shot.format(n=n, m=n + 1) for n in (1, 2, 3)) + "\n"
        self.assertEqual(self.strip(prompt).count("[Shot "), 1)


@unittest.skipIf(torch is None, "PyTorch is not installed")
class AudioSwitchTests(unittest.TestCase):
    def setUp(self):
        self.audio = load_module("audio_mode")

    def test_crop_cuts_the_start_and_length_in_samples(self):
        data = torch.arange(100.0).reshape(1, 100)
        self.assertEqual(self.audio.crop_waveform(data, 10, 2.0, 3.0).tolist(), [list(range(20, 50))])
        self.assertEqual(self.audio.crop_waveform(torch.zeros(2, 100), 10, 9.0, 0).shape, (2, 10))
        with self.assertRaises(ValueError):
            self.audio.crop_waveform(torch.zeros(2, 100), 10, 10.0, 1.0)

    def test_built_in_audio_gives_no_song_and_needs_no_file(self):
        self.assertEqual(self.audio.VRGDG_MiniMaxH3AudioSource().load(True, "", 0, 12), (None, True))

    def test_my_song_needs_a_file(self):
        with self.assertRaisesRegex(ValueError, "built_in_audio"):
            self.audio.VRGDG_MiniMaxH3AudioSource().load(False, "", 0, 0)

    def test_my_song_loads_the_scene_part(self):
        try:
            import comfy_extras.nodes_audio  # noqa: F401
        except Exception:
            self.skipTest("ComfyUI is not importable")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "song.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(8000)
                handle.writeframes(b"\0\0" * 8000 * 5)
            song, built_in = self.audio.VRGDG_MiniMaxH3AudioSource().load(False, str(path), 1.0, 2.0)
        self.assertFalse(built_in)
        self.assertEqual(tuple(song["waveform"].shape), (1, 1, 16000))

    def test_built_in_audio_skips_the_lock_and_my_song_is_the_soundtrack(self):
        latent = {"samples": "untouched"}
        self.assertIs(self.audio.VRGDG_MiniMaxH3AudioLockSwitch().apply(latent, None, True)[0], latent)
        song = {"waveform": torch.zeros(1, 1, 10), "sample_rate": 8000}
        self.assertIs(self.audio.VRGDG_MiniMaxH3VideoSoundtrack().pick({}, None, False, song)[0], song)

    def test_my_song_mode_without_a_song_is_refused(self):
        with self.assertRaises(ValueError):
            self.audio.VRGDG_MiniMaxH3AudioLockSwitch().apply({}, None, False, None)
        with self.assertRaises(ValueError):
            self.audio.VRGDG_MiniMaxH3VideoSoundtrack().pick({}, None, False, None)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        cls.nodes = {node["id"]: node for node in cls.workflow["nodes"]}
        cls.links = {link[0]: link for link in cls.workflow["links"]}

    def titled(self, title):
        found = [node for node in self.nodes.values() if node.get("title") == title]
        self.assertEqual(len(found), 1, title)
        return found[0]

    def one(self, class_type):
        found = [node for node in self.nodes.values() if node["type"] == class_type]
        self.assertEqual(len(found), 1, class_type)
        return found[0]

    def source(self, node, name):
        entry = next(item for item in node["inputs"] if item["name"] == name)
        link = self.links[entry["link"]]
        return self.nodes[link[1]]["type"], link[2]

    def test_every_link_is_recorded_on_both_ends(self):
        for link_id, origin, slot, target, target_slot, _kind in self.workflow["links"]:
            self.assertIn(link_id, self.nodes[origin]["outputs"][slot]["links"])
            self.assertEqual(self.nodes[target]["inputs"][target_slot]["link"], link_id)

    def test_vrgdg_nodes_are_this_folder_or_the_two_builder_nodes(self):
        source = (NODE_FOLDER / "__init__.py").read_text(encoding="utf-8")
        own = {"VRGDG_MiniMaxH3Pass2PromptNoTiming", "VRGDG_MiniMaxH3AudioSource",
               "VRGDG_MiniMaxH3AudioLockSwitch", "VRGDG_MiniMaxH3VideoSoundtrack"}
        used = {node["type"] for node in self.nodes.values() if node["type"].startswith("VRGDG_")}
        self.assertEqual(used, own | BUILDER_NODES)
        for name in own:
            self.assertIn(name, (NODE_FOLDER / ("pass2_prompt.py" if "Prompt" in name else "audio_mode.py"))
                          .read_text(encoding="utf-8"))
        self.assertIn("audio_mode", source)

    def test_dmad_and_window_values_are_the_builder_defaults(self):
        self.assertEqual(self.titled("PASS 1 - DMAD 4-step LoRA")["widgets_values"], list(DMAD["dmad_lora"]))
        self.assertEqual(self.titled("PASS 2 - Refiner LoRA (DMAD)")["widgets_values"], list(DMAD["refiner_lora"]))
        sampler, scheduler, steps, denoise = DMAD["pass1"]
        self.assertEqual(self.titled("PASS 1 - Sampler (lcm)")["widgets_values"], [sampler])
        self.assertEqual(self.titled("PASS 1 - Scheduler (DMAD 4 steps)")["widgets_values"], [scheduler, steps, denoise])
        self.assertEqual(self.one("MiniMaxH3SigmaShift")["widgets_values"], list(DMAD["shift"]))
        sampler2, steps2, denoise2 = DMAD["pass2"]
        self.assertEqual(self.titled("INPUT - Pass 2 Sampler")["widgets_values"], [sampler2])
        self.assertEqual(self.titled("INPUT - Refinement Schedule Steps")["widgets_values"][0], steps2)
        self.assertEqual(self.titled("INPUT - Refinement Denoise")["widgets_values"][0], denoise2)
        values = self.one("VRGDG_MiniMaxH3ChunkedPass2")["widgets_values"]
        self.assertEqual(values[1:4], [WINDOWS["chunk_seconds"], WINDOWS["overlap_seconds"], WINDOWS["overlap_mode"]])
        self.assertEqual(values[6], WINDOWS["tail_trim_seconds"])
        self.assertEqual(values[8], WINDOWS["upscale"])

    def test_one_switch_drives_every_audio_choice(self):
        self.assertIs(self.one("VRGDG_MiniMaxH3AudioSource")["widgets_values"][0], False)
        for class_type in ("VRGDG_MiniMaxH3AudioLockSwitch", "VRGDG_MiniMaxH3VideoSoundtrack"):
            node = self.one(class_type)
            self.assertEqual(self.source(node, "built_in_audio"), ("VRGDG_MiniMaxH3AudioSource", 1))
            self.assertEqual(self.source(node, "song"), ("VRGDG_MiniMaxH3AudioSource", 0))
        for node in self.nodes.values():
            if node["type"] == "MiniMaxH3ReferenceToVideo":
                self.assertEqual(self.source(node, "ref_audios.ref_audio_0"), ("VRGDG_MiniMaxH3AudioSource", 0))
        sampler = self.titled("PASS 1 - Sampler (low resolution)")
        self.assertEqual(self.source(sampler, "latent_image"), ("VRGDG_MiniMaxH3AudioLockSwitch", 0))
        self.assertEqual(self.source(self.one("VRGDG_MiniMaxH3VideoSoundtrack"), "av_latent"), ("SamplerCustomAdvanced", 0))
        self.assertEqual(self.source(self.one("VHS_VideoCombine"), "audio"), ("VRGDG_MiniMaxH3VideoSoundtrack", 0))

    def test_the_windows_read_the_prompt_without_lyric_times(self):
        strip = self.one("VRGDG_MiniMaxH3Pass2PromptNoTiming")
        self.assertEqual(self.source(strip, "prompt"), ("PrimitiveStringMultiline", 0))
        conditioning = self.titled("PASS 2 - Conditioning for the windows")
        self.assertEqual(self.source(conditioning, "prompt"), ("VRGDG_MiniMaxH3Pass2PromptNoTiming", 0))
        self.assertEqual(self.source(self.one("VRGDG_MiniMaxH3ChunkedPass2"), "conditioning"),
                         ("MiniMaxH3ReferenceToVideo", 0))
        self.assertEqual(self.source(self.one("VAEDecode"), "samples"), ("VRGDG_MiniMaxH3ChunkedPass2", 0))

    def test_only_seeds_change_between_runs(self):
        for node in self.nodes.values():
            values = node["widgets_values"]
            if isinstance(values, list) and "randomize" in values:
                self.assertIn(node["type"], {"RandomNoise", "VRGDG_MiniMaxH3ChunkedPass2"}, node["title"])

    def test_every_node_sits_inside_one_group_and_every_group_has_a_note(self):
        for node in self.nodes.values():
            x, y = node["pos"]
            inside = [group for group in self.workflow["groups"]
                      if group["bounding"][0] <= x <= group["bounding"][0] + group["bounding"][2]
                      and group["bounding"][1] <= y <= group["bounding"][1] + group["bounding"][3]]
            self.assertEqual(len(inside), 1, node["title"])
        notes = [node for node in self.nodes.values() if node["type"] == "MarkdownNote"]
        self.assertEqual(len(notes), len(self.workflow["groups"]))


if __name__ == "__main__":
    unittest.main()
