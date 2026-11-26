"""The ai-images skill's `gen.py`.

It sends one prompt to a diffusers text-to-image model and saves a PNG.
torch and diffusers are not imported by the test run: `main` imports
them late, so a pair of stand-ins in `sys.modules` exercise every branch
without a GPU or a download. What the stand-ins cannot show, that a real
klein 4B run writes a real image, is the hand-run smoke test in the PR
that added the skill.

Loaded by path: the skill folder's name has a hyphen.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "ai-images"
    / "scripts"
    / "gen.py"
)
_SPEC = importlib.util.spec_from_file_location("ai_images_gen", SCRIPT)
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)

KLEIN = "black-forest-labs/FLUX.2-klein-4B"


class FakeGenerator:
    def __init__(self, device):
        self.device = device
        self.seed = None

    def manual_seed(self, seed):
        self.seed = seed
        return self


def fake_torch(cuda=True, mps=False):
    return types.SimpleNamespace(
        bfloat16="bf16",
        Generator=FakeGenerator,
        cuda=types.SimpleNamespace(is_available=lambda: cuda),
        backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: mps)),
    )


class FakeImage:
    def save(self, path):
        Path(path).write_bytes(b"png")


class FakePipe:
    """Records what `from_pretrained` and the call were given."""

    loaded = {}
    called = {}

    @classmethod
    def from_pretrained(cls, model, **kwargs):
        cls.loaded = {"model": model, **kwargs}
        return cls()

    def to(self, device):
        FakePipe.loaded["device"] = device
        return self

    def __call__(self, **kwargs):
        FakePipe.called = kwargs
        return types.SimpleNamespace(images=[FakeImage()])


@pytest.fixture(name="stand_ins")
def _stand_ins(monkeypatch):
    """torch and diffusers as `main` imports them, on a CUDA host."""
    FakePipe.loaded, FakePipe.called = {}, {}
    monkeypatch.setitem(sys.modules, "torch", fake_torch())
    monkeypatch.setitem(sys.modules, "diffusers", types.SimpleNamespace(DiffusionPipeline=FakePipe))


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("AI_IMAGES_MODEL", raising=False)
        args = gen.parse_args(["a lighthouse"])
        assert (args.prompt, args.model, args.out) == ("a lighthouse", KLEIN, Path("ai-image.png"))
        assert (args.seed, args.steps, args.width, args.height) == (None, None, 1024, 1024)

    def test_the_environment_picks_the_model(self, monkeypatch):
        monkeypatch.setenv("AI_IMAGES_MODEL", "some/model")
        assert gen.parse_args(["x"]).model == "some/model"

    def test_the_flag_beats_the_environment(self, monkeypatch):
        monkeypatch.setenv("AI_IMAGES_MODEL", "some/model")
        assert gen.parse_args(["x", "--model", "other/model"]).model == "other/model"


class TestSamplerSettings:
    def test_a_distilled_klein_runs_four_steps_without_guidance(self):
        assert gen.sampler_settings(KLEIN) == {"num_inference_steps": 4, "guidance_scale": 1.0}

    def test_a_base_klein_is_not_distilled(self):
        assert gen.sampler_settings("black-forest-labs/FLUX.2-klein-base-4B") == {}

    def test_any_other_model_keeps_the_pipelines_defaults(self):
        assert gen.sampler_settings("black-forest-labs/FLUX.2-dev") == {}


class TestPickDevice:
    def test_cuda_first(self):
        assert gen.pick_device(fake_torch(cuda=True, mps=True)) == "cuda"

    def test_then_metal(self):
        assert gen.pick_device(fake_torch(cuda=False, mps=True)) == "mps"

    def test_with_neither_it_refuses_rather_than_run_on_the_cpu(self):
        with pytest.raises(SystemExit) as refused:
            gen.pick_device(fake_torch(cuda=False, mps=False))
        assert "CPU run would take hours" in str(refused.value)


@pytest.mark.usefixtures("stand_ins")
class TestMain:
    def test_it_saves_the_image_and_says_where_model_and_seed(self, tmp_path, capsys):
        out = tmp_path / "deep" / "x.png"
        gen.main(["a prompt", "--out", str(out), "--seed", "7"])
        assert out.read_bytes() == b"png"
        assert f"saved {out.resolve()} (model {KLEIN}, seed 7)" in capsys.readouterr().out

    def test_the_model_loads_in_bf16_on_the_picked_device(self, tmp_path):
        gen.main(["p", "--out", str(tmp_path / "x.png"), "--seed", "1"])
        assert FakePipe.loaded == {
            "model": KLEIN,
            "torch_dtype": "bf16",
            "device": "cuda",
        }

    def test_the_call_gets_the_prompt_size_seed_and_klein_settings(self, tmp_path):
        gen.main(["a prompt", "--out", str(tmp_path / "x.png"), "--seed", "9", "--width", "512"])
        called = FakePipe.called
        assert (called["prompt"], called["width"], called["height"]) == ("a prompt", 512, 1024)
        assert called["generator"].seed == 9
        assert called["num_inference_steps"] == 4

    def test_steps_overrides_the_models_default(self, tmp_path):
        gen.main(["p", "--out", str(tmp_path / "x.png"), "--seed", "1", "--steps", "8"])
        assert FakePipe.called["num_inference_steps"] == 8

    def test_an_omitted_seed_is_random_and_printed(self, tmp_path, capsys):
        gen.main(["p", "--out", str(tmp_path / "x.png")])
        seed = FakePipe.called["generator"].seed
        assert 0 <= seed < 2**32
        assert f"seed {seed})" in capsys.readouterr().out
