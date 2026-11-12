"""Tests for adding --upload-dir to the voice search path."""

import argparse
from pathlib import Path
from typing import List

from wyoming_piper.__main__ import _add_upload_dir


def _args(data_dirs: List[Path], upload_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        data_dir=[str(d) for d in data_dirs],
        upload_dir=str(upload_dir),
    )


def test_unlisted_upload_dir_searched_first(tmp_path: Path) -> None:
    """Uploads must be found, and win over a catalog copy of the same name."""
    downloads = tmp_path / "downloads"
    shared = tmp_path / "shared"
    uploads = tmp_path / "uploads"
    args = _args([downloads, shared], uploads)

    _add_upload_dir(args)

    assert args.data_dir == [str(uploads), str(downloads), str(shared)]


def test_listed_upload_dir_keeps_its_place(tmp_path: Path) -> None:
    """An explicit position in --data-dir is the user's choice."""
    downloads = tmp_path / "downloads"
    uploads = tmp_path / "uploads"
    args = _args([downloads, uploads], uploads)

    _add_upload_dir(args)

    assert args.data_dir == [str(downloads), str(uploads)]


def test_listed_upload_dir_matched_by_resolved_path(tmp_path: Path) -> None:
    """A differently spelled path to a listed dir is not added again."""
    downloads = tmp_path / "downloads"
    uploads = tmp_path / "uploads"
    args = _args([downloads, uploads], tmp_path / "downloads" / ".." / "uploads")

    _add_upload_dir(args)

    assert args.data_dir == [str(downloads), str(uploads)]
