"""Tests for the voice management web UI."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytest.importorskip("flask", reason="requires the 'web' optional dependencies")

from wyoming_piper.web_server import make_web_server  # noqa: E402


def _write_voice(data_dir: Path, name: str, dataset: str) -> None:
    (data_dir / f"{name}.onnx").write_bytes(b"x" * 1024)
    (data_dir / f"{name}.onnx.json").write_text(
        json.dumps(
            {
                "audio": {"sample_rate": 22050, "quality": "medium"},
                "language": {"code": "en_US"},
                "dataset": dataset,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(name="dirs")
def dirs_fixture(tmp_path: Path) -> List[Path]:
    """Two data dirs plus a separate download dir."""
    dirs = [tmp_path / "data1", tmp_path / "data2", tmp_path / "downloads"]
    for path in dirs:
        path.mkdir()

    _write_voice(dirs[0], "in-data1", "in-data1")
    _write_voice(dirs[1], "in-data2", "in-data2")
    _write_voice(dirs[2], "in-downloads", "in-downloads")
    # Same name in two data dirs: the first should win, as in find_voice()
    _write_voice(dirs[0], "shadowed", "from-data1")
    _write_voice(dirs[1], "shadowed", "from-data2")
    return dirs


@pytest.fixture(name="client")
def client_fixture(dirs: List[Path]) -> Any:
    args = argparse.Namespace(
        backend="piper",
        data_dir=[str(dirs[0]), str(dirs[1])],
        download_dir=str(dirs[2]),
        omnivoice_ref_dir=None,
        omnivoice_language="English",
    )
    return make_web_server(args).test_client()


def _voices(client: Any) -> Dict[str, Dict[str, Any]]:
    return {v["name"]: v for v in client.get("/api/piper/voices").get_json()["voices"]}


def test_lists_voices_from_every_data_dir(client: Any) -> None:
    """Voices are advertised from every --data-dir, so all are managed."""
    names = _voices(client)
    assert {"in-data1", "in-data2", "in-downloads"} <= set(names)


def test_shadowed_voice_listed_once_from_first_data_dir(
    client: Any, dirs: List[Path]
) -> None:
    """A duplicated name resolves the way the Wyoming server resolves it."""
    voice = _voices(client)["shadowed"]
    assert voice["dir"] == str(dirs[0])
    assert voice["dataset"] == "from-data1"


def test_delete_removes_every_copy(client: Any, dirs: List[Path]) -> None:
    """Leaving a shadowed copy behind would keep the voice advertised."""
    response = client.post("/api/piper/delete", data={"name": "shadowed"})
    assert response.status_code == 200
    assert response.get_json()["ok"]

    for data_dir in dirs:
        assert not (data_dir / "shadowed.onnx").exists()
        assert not (data_dir / "shadowed.onnx.json").exists()


def test_delete_outside_download_dir(client: Any, dirs: List[Path]) -> None:
    """Deleting is not limited to --download-dir."""
    response = client.post("/api/piper/delete", data={"name": "in-data2"})
    assert response.status_code == 200
    assert not (dirs[1] / "in-data2.onnx").exists()


def test_delete_unknown_voice_is_404(client: Any) -> None:
    response = client.post("/api/piper/delete", data={"name": "nope"})
    assert response.status_code == 404


def test_delete_rejects_path_traversal(client: Any) -> None:
    for name in ("../escape", "..", "a/b"):
        response = client.post("/api/piper/delete", data={"name": name})
        assert response.status_code == 400, name


def test_status_reports_managed_dirs(client: Any, dirs: List[Path]) -> None:
    status = client.get("/api/status").get_json()
    assert status["voice_dirs"] == [str(d) for d in dirs]
    assert status["download_dir"] == str(dirs[2])
