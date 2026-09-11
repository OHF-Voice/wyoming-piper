"""Tests for restricting the web UI to an allow list of peer addresses.

The UI has no authentication, so when its bind address is reachable by more
than the intended client -- as it is behind Home Assistant ingress, where the
server must bind a routable address to receive from the proxy -- the peer
address is the only thing left to filter on.
"""

import argparse
from pathlib import Path
from typing import Any, List, Optional

import pytest

pytest.importorskip("flask", reason="requires the 'web' optional dependencies")

from wyoming_piper.web_server import make_web_server, parse_allow_list  # noqa: E402

_INGRESS = "172.30.32.2"


def _client(tmp_path: Path, allow: Optional[List[str]]) -> Any:
    args = argparse.Namespace(
        backend="piper",
        data_dir=[str(tmp_path)],
        download_dir=str(tmp_path),
        omnivoice_ref_dir=None,
        omnivoice_language="English",
        web_server_allow=allow,
    )
    return make_web_server(args).test_client()


def _status(client: Any, remote_addr: str) -> int:
    return client.get(
        "/api/status", environ_base={"REMOTE_ADDR": remote_addr}
    ).status_code


def test_no_allow_list_serves_everyone(tmp_path: Path) -> None:
    """Default behaviour is unchanged, so existing setups keep working."""
    client = _client(tmp_path, None)

    assert _status(client, _INGRESS) == 200
    assert _status(client, "10.0.0.5") == 200


def test_allowed_address_is_served(tmp_path: Path) -> None:
    client = _client(tmp_path, [_INGRESS])

    assert _status(client, _INGRESS) == 200


@pytest.mark.parametrize(
    "remote_addr",
    [
        pytest.param("172.30.32.3", id="neighbouring_address"),
        pytest.param("10.0.0.5", id="another_subnet"),
        pytest.param("127.0.0.1", id="loopback_is_not_implicitly_allowed"),
    ],
)
def test_other_addresses_are_rejected(tmp_path: Path, remote_addr: str) -> None:
    client = _client(tmp_path, [_INGRESS])

    assert _status(client, remote_addr) == 403


def test_cidr_range(tmp_path: Path) -> None:
    client = _client(tmp_path, ["172.30.32.0/24"])

    assert _status(client, "172.30.32.99") == 200
    assert _status(client, "172.30.33.1") == 403


def test_several_entries(tmp_path: Path) -> None:
    client = _client(tmp_path, [_INGRESS, "127.0.0.1"])

    assert _status(client, _INGRESS) == 200
    assert _status(client, "127.0.0.1") == 200
    assert _status(client, "10.0.0.5") == 403


def test_ipv4_mapped_ipv6_peer_matches_an_ipv4_rule(tmp_path: Path) -> None:
    """A dual-stack listener reports IPv4 peers as ::ffff:a.b.c.d."""
    client = _client(tmp_path, [_INGRESS])

    assert _status(client, f"::ffff:{_INGRESS}") == 200
    assert _status(client, "::ffff:10.0.0.5") == 403


@pytest.mark.parametrize(
    "remote_addr",
    [pytest.param("", id="empty"), pytest.param("not-an-address", id="unparseable")],
)
def test_unusable_peer_address_is_rejected(tmp_path: Path, remote_addr: str) -> None:
    client = _client(tmp_path, [_INGRESS])

    assert _status(client, remote_addr) == 403


def test_uploads_are_blocked_before_the_body_is_read(tmp_path: Path) -> None:
    """The check is the outermost layer, so writes cannot slip past it."""
    client = _client(tmp_path, [_INGRESS])

    response = client.post(
        "/api/piper/delete",
        data={"name": "anything"},
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
    )

    assert response.status_code == 403


def test_invalid_entry_is_reported(tmp_path: Path) -> None:
    """__main__ turns this into a startup error rather than a silent deny-all."""
    with pytest.raises(ValueError):
        parse_allow_list(["172.30.32.999"])
