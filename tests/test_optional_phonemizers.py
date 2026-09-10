"""Tests for voices whose phonemizer is an optional dependency.

Japanese and Thai voices need ``pyopenjtalk`` and ``tltk``. Advertising one
without its phonemizer means the client offers the voice and every request
answers with silence, so they have to be left out of the Wyoming info.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from wyoming_piper.__main__ import _piper_info, _setup_piper

_JAPANESE = "ja_JA-hi_fi_captain-medium"
_THAI = "th_TH-tsync2-medium"
_ENGLISH = "en_US-lessac-medium"


def _catalog() -> Dict[str, Any]:
    """A stand-in for voices.json with one voice per language of interest."""
    return {
        name: {
            "key": name,
            "name": name.split("-")[1],
            "quality": "medium",
            "language": {"code": code},
            "files": {},
        }
        for name, code in (
            (_JAPANESE, "ja_JA"),
            (_THAI, "th_TH"),
            (_ENGLISH, "en_US"),
        )
    }


def _args(data_dir: Path, voice: str = _ENGLISH) -> argparse.Namespace:
    return argparse.Namespace(
        backend="piper",
        voice=voice,
        data_dir=[str(data_dir)],
        download_dir=str(data_dir),
        update_voices=False,
        no_streaming=False,
    )


def _advertised(info: Any) -> List[str]:
    return [voice.name for voice in info.tts[0].voices]


def _install(monkeypatch: pytest.MonkeyPatch, *modules: str) -> None:
    """Pretend exactly ``modules`` of the optional phonemizers are installed."""
    import wyoming_piper.__main__ as main_module

    real_find_spec = main_module.importlib.util.find_spec

    def fake_find_spec(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in ("pyopenjtalk", "tltk", "g2pw"):
            return object() if name in modules else None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(main_module.importlib.util, "find_spec", fake_find_spec)


def test_catalog_voices_hidden_without_phonemizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Japanese and Thai are dropped when neither phonemizer is installed."""
    _install(monkeypatch)

    names = _advertised(_piper_info(_args(tmp_path), _catalog()))

    assert _ENGLISH in names
    assert _JAPANESE not in names
    assert _THAI not in names


def test_catalog_voices_shown_with_phonemizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each voice comes back as soon as its own phonemizer is available."""
    _install(monkeypatch, "pyopenjtalk")

    names = _advertised(_piper_info(_args(tmp_path), _catalog()))

    assert _JAPANESE in names
    assert _THAI not in names


def test_chinese_is_never_filtered_by_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chinese voices are a mix of pinyin and espeak, so language cannot decide.

    ``zh_CN-huayan-medium`` is an espeak voice and works without the ``zh``
    extra; filtering the whole language would hide it.
    """
    _install(monkeypatch)
    catalog = _catalog()
    catalog["zh_CN-huayan-medium"] = {
        "key": "zh_CN-huayan-medium",
        "name": "huayan",
        "quality": "medium",
        "language": {"code": "zh_CN"},
        "files": {},
    }

    assert "zh_CN-huayan-medium" in _advertised(_piper_info(_args(tmp_path), catalog))


def _write_custom_voice(data_dir: Path, name: str, phoneme_type: Optional[str]) -> None:
    config: Dict[str, Any] = {
        "audio": {"sample_rate": 22050, "quality": "medium"},
        "language": {"code": "en_US"},
        "dataset": name,
    }
    if phoneme_type is not None:
        config["phoneme_type"] = phoneme_type

    (data_dir / f"{name}.onnx").touch()
    (data_dir / f"{name}.onnx.json").write_text(json.dumps(config), encoding="utf-8")


@pytest.mark.parametrize(
    ("phoneme_type", "installed", "expected"),
    [
        pytest.param("thai", (), False, id="thai_without_tltk"),
        pytest.param("thai", ("tltk",), True, id="thai_with_tltk"),
        pytest.param("pinyin", (), False, id="pinyin_without_g2pw"),
        pytest.param("pinyin", ("g2pw",), True, id="pinyin_with_g2pw"),
        pytest.param("espeak", (), True, id="espeak_needs_nothing"),
        pytest.param(None, (), True, id="unset_defaults_to_espeak"),
    ],
)
def test_custom_voice_uses_its_phoneme_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phoneme_type: Optional[str],
    installed: "tuple[str, ...]",
    expected: bool,
) -> None:
    """A custom voice's config states its phoneme type, so no guessing needed."""
    _install(monkeypatch, *installed)
    _write_custom_voice(tmp_path, "my_custom_voice", phoneme_type)

    names = _advertised(_piper_info(_args(tmp_path), _catalog()))

    assert ("my_custom_voice" in names) is expected


def test_default_voice_without_phonemizer_is_a_startup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--voice pointing at an unusable voice fails now, not on first request."""
    _install(monkeypatch)
    monkeypatch.setattr(
        "wyoming_piper.__main__.get_voices", lambda *args, **kwargs: _catalog()
    )

    with pytest.raises(ValueError, match=r"wyoming-piper\[th\]"):
        _setup_piper(_args(tmp_path, voice=_THAI))
