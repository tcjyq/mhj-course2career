import hashlib

from course2career.ui.installation import (
    InstallationState,
    installation_hash,
    parse_installation_state,
)


def test_installation_state_distinguishes_async_and_unavailable():
    marker = "A" * 43
    assert parse_installation_state(None) == InstallationState("PENDING")
    assert parse_installation_state({}) == InstallationState("PENDING")
    assert parse_installation_state({"ready": True, "value": marker}) == (
        InstallationState("PRESENT", marker)
    )
    assert parse_installation_state({"ready": True, "value": "short"}) == (
        InstallationState("UNAVAILABLE")
    )
    assert parse_installation_state({"ready": True, "unavailable": True}) == (
        InstallationState("UNAVAILABLE")
    )


def test_only_opaque_marker_is_hashed():
    marker = "A" * 43
    assert installation_hash(marker) == hashlib.sha256(marker.encode()).hexdigest()
    assert installation_hash("bad") is None
    assert installation_hash(None) is None
