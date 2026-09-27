"""Validate and hash a random installation marker without retaining plaintext."""

import hashlib
import re

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def installation_hash(value: str | None) -> str | None:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        return None
    return hashlib.sha256(value.encode("ascii")).hexdigest()
