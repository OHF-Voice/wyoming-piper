import sys
from types import ModuleType, SimpleNamespace

import pytest

from wyoming_piper.omnivoice import OmniVoiceModel


@pytest.mark.parametrize(
    ("use_cuda", "expected_providers"),
    [
        (False, ["CPUExecutionProvider"]),
        (True, ["CUDAExecutionProvider", "CPUExecutionProvider"]),
    ],
)
def test_execution_providers(monkeypatch, use_cuda, expected_providers) -> None:
    captured = {}

    class FakeInferenceSession:
        def __init__(self, _path, _options, providers):
            captured["providers"] = providers

        def get_inputs(self):
            return []

    class FakeOmniVoice:
        sampling_rate = 24000

        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

        def eval(self) -> None:
            pass

    fake_ort = SimpleNamespace(
        GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL=1),
        InferenceSession=FakeInferenceSession,
        SessionOptions=lambda: SimpleNamespace(graph_optimization_level=None),
    )
    fake_torch = SimpleNamespace(float32="float32")
    fake_omnivoice = ModuleType("omnivoice.models.omnivoice")
    fake_omnivoice.OmniVoice = FakeOmniVoice
    fake_omnivoice.OmniVoiceModelOutput = object

    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "omnivoice", ModuleType("omnivoice"))
    monkeypatch.setitem(sys.modules, "omnivoice.models", ModuleType("omnivoice.models"))
    monkeypatch.setitem(sys.modules, "omnivoice.models.omnivoice", fake_omnivoice)

    OmniVoiceModel("model.onnx", use_cuda=use_cuda)

    assert captured["providers"] == expected_providers
