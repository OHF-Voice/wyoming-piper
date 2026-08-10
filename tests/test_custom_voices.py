"""Tests for custom voice discovery and naming."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from wyoming_piper.__main__ import _setup_piper

_MISMATCHED = "en_GB-jarvis-medium"  # config says dataset="jarvis-medium"
_MATCHED = "en_US-custom-high"


def _write_voice(data_dir: Path, file_name: str, dataset: Optional[str]) -> None:
    config: Dict[str, Any] = {
        "audio": {"sample_rate": 22050, "quality": "medium"},
        "language": {"code": "en_GB"},
    }
    if dataset is not None:
        config["dataset"] = dataset

    (data_dir / f"{file_name}.onnx").touch()
    (data_dir / f"{file_name}.onnx.json").write_text(
        json.dumps(config), encoding="utf-8"
    )


@pytest.fixture(name="data_dir")
def data_dir_fixture(tmp_path: Path) -> Path:
    _write_voice(tmp_path, _MISMATCHED, dataset="jarvis-medium")
    _write_voice(tmp_path, _MATCHED, dataset=_MATCHED)
    return tmp_path


@pytest.fixture(name="setup_result")
def setup_result_fixture(data_dir: Path) -> "tuple[Any, Dict[str, Any]]":
    args = argparse.Namespace(
        backend="piper",
        voice=_MATCHED,
        data_dir=[str(data_dir)],
        download_dir=str(data_dir),
        update_voices=False,
        no_streaming=False,
    )
    return _setup_piper(args)


def _resolve(voices_info: Dict[str, Any], name: str) -> str:
    """Resolve a requested voice name the way the event handler does."""
    return voices_info.get(name, {}).get("key", name)


@pytest.mark.parametrize(
    ("file_name", "description"),
    [
        pytest.param(_MISMATCHED, "jarvis-medium (medium)", id="dataset_mismatch"),
        pytest.param(_MATCHED, f"{_MATCHED} (medium)", id="dataset_match"),
    ],
)
def test_custom_voice_advertised_by_file_name(
    setup_result: "tuple[Any, Dict[str, Any]]", file_name: str, description: str
) -> None:
    """Custom voices are advertised under their file name, not "dataset"."""
    wyoming_info, _voices_info = setup_result
    voice = next(
        (v for v in wyoming_info.tts[0].voices if v.name == file_name),
        None,
    )
    assert voice is not None
    assert voice.description == description


def test_advertised_custom_voice_names_are_resolvable(
    setup_result: "tuple[Any, Dict[str, Any]]", data_dir: Path
) -> None:
    """Every advertised custom voice name can be loaded again."""
    wyoming_info, voices_info = setup_result
    for name in (_MISMATCHED, _MATCHED):
        assert (data_dir / f"{_resolve(voices_info, name)}.onnx").exists()

    assert not any(v.name == "jarvis-medium" for v in wyoming_info.tts[0].voices)


def test_dataset_name_still_accepted(
    setup_result: "tuple[Any, Dict[str, Any]]", data_dir: Path
) -> None:
    """The previously advertised "dataset" name is kept as an alias."""
    _wyoming_info, voices_info = setup_result
    assert _resolve(voices_info, "jarvis-medium") == _MISMATCHED
    assert (data_dir / f"{_MISMATCHED}.onnx").exists()


def test_catalog_voice_not_shadowed_by_dataset_alias(data_dir: Path) -> None:
    """A "dataset" alias never overrides a real catalog voice."""
    _write_voice(data_dir, "my-copy-of-lessac", dataset="en_US-lessac-medium")
    args = argparse.Namespace(
        backend="piper",
        voice=_MATCHED,
        data_dir=[str(data_dir)],
        download_dir=str(data_dir),
        update_voices=False,
        no_streaming=False,
    )
    _wyoming_info, voices_info = _setup_piper(args)

    assert _resolve(voices_info, "en_US-lessac-medium") == "en_US-lessac-medium"
