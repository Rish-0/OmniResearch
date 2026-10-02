"""UUIDv7 ID generation (time-ordered UUIDs per RFC 9562)."""

from __future__ import annotations

import os
import time
from uuid import UUID


def uuid7() -> UUID:
    """Generate a UUIDv7 (time-ordered, random) per RFC 9562.

    Layout (128 bits):
      48-bit unix_ts_ms | 4-bit version (0b0111) | 12-bit rand_a |
      2-bit variant (0b10) | 62-bit rand_b
    """
    timestamp_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)  # 80 bits of randomness

    # 48-bit timestamp
    uuid_int = (timestamp_ms & 0xFFFFFFFFFFFF) << 80

    # Version 7 (4 bits)
    uuid_int |= 0x7 << 76

    # rand_a (12 bits from first random bytes)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF
    uuid_int |= rand_a << 64

    # Variant (2 bits = 0b10)
    uuid_int |= 0x2 << 62

    # rand_b (62 bits from remaining random bytes)
    rand_b = int.from_bytes(rand_bytes[2:], "big") & 0x3FFFFFFFFFFFFFFF
    uuid_int |= rand_b

    return UUID(int=uuid_int)
