import sys
from types import ModuleType, SimpleNamespace

import pytest

from wyoming_piper.omnivoice import OmniVoiceModel


def _patch_modules(monkeypatch, ep_devices) -> dict:
    """Patch onnxruntime, the OpenVINO plugin EP, and omnivoice with fakes.

    ``ep_devices`` is a list of ov_device names exposed by the fake EP.
    Returns a dict capturing what OmniVoiceModel did with the fakes.
    """
    captured = {}

    class FakeSessionOptions:
        def __init__(self) -> None:
            self.graph_optimization_level = None
            self.provider_devices = None

        def add_provider_for_devices(self, devices, options):
            self.provider_devices = (devices, options)

    class FakeInferenceSession:
        def __init__(self, _path, _options, providers=None):
            captured["options"] = _options
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

    def register_execution_provider_library(name, path):
        captured["registered"] = (name, path)

    fake_ort = SimpleNamespace(
        GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL=1),
        InferenceSession=FakeInferenceSession,
        SessionOptions=FakeSessionOptions,
        register_execution_provider_library=register_execution_provider_library,
        get_ep_devices=lambda: [
            SimpleNamespace(
                ep_name="OpenVINOExecutionProvider",
                ep_metadata={"ov_device": ov_device},
            )
            for ov_device in ep_devices
        ],
    )
    fake_ep = SimpleNamespace(
        get_library_path=lambda: "/ep/libonnxruntime_providers_openvino_plugin.so",
        get_ep_name=lambda: "OpenVINOExecutionProvider",
    )
    fake_torch = SimpleNamespace(float32="float32")
    fake_omnivoice = ModuleType("omnivoice.models.omnivoice")
    fake_omnivoice.OmniVoice = FakeOmniVoice
    fake_omnivoice.OmniVoiceModelOutput = object

    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setitem(sys.modules, "onnxruntime_ep_openvino", fake_ep)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "omnivoice", ModuleType("omnivoice"))
    monkeypatch.setitem(sys.modules, "omnivoice.models", ModuleType("omnivoice.models"))
    monkeypatch.setitem(sys.modules, "omnivoice.models.omnivoice", fake_omnivoice)

    return captured


def test_openvino_device(monkeypatch) -> None:
    captured = _patch_modules(monkeypatch, ["CPU", "GPU"])

    OmniVoiceModel("model.onnx", openvino_device="GPU")

    assert captured["registered"] == (
        "openvino_ep",
        "/ep/libonnxruntime_providers_openvino_plugin.so",
    )
    # Plugin EPs are attached to the session options, not the providers= list.
    assert captured["providers"] is None
    device_list, ep_options = captured["options"].provider_devices
    assert [d.ep_metadata["ov_device"] for d in device_list] == ["GPU"]
    assert ep_options == {}


def test_openvino_device_unavailable(monkeypatch) -> None:
    _patch_modules(monkeypatch, ["CPU"])

    with pytest.raises(RuntimeError, match="OpenVINO device 'GPU' not available.*CPU"):
        OmniVoiceModel("model.onnx", openvino_device="GPU")
