"""Shared validation, matching, and difficulty helpers for vanity searches."""

from __future__ import annotations

from typing import Tuple


BITCOIN_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ETHEREUM_ALPHABET = "0123456789abcdef"
TOR_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
SUPPORTED_CRYPTOS = {"bitcoin", "ethereum", "tor"}
SUPPORTED_POSITIONS = {"start", "end", "both", "anywhere"}


def normalize_pattern(pattern: str, crypto: str) -> str:
    stripped = pattern.strip()
    if crypto in {"ethereum", "tor"}:
        return stripped.lower()
    return stripped


def validate_pattern(pattern: str, crypto: str) -> Tuple[bool, str]:
    """Validate that a search pattern can appear in the selected address type."""
    if crypto not in SUPPORTED_CRYPTOS:
        return False, f"Unsupported target: {crypto}"

    normalized = normalize_pattern(pattern, crypto)
    if not normalized:
        return True, ""

    if crypto == "bitcoin":
        alphabet = BITCOIN_ALPHABET
        label = "Bitcoin addresses use Base58 characters: 1-9, A-Z, a-z except 0, O, I, and l."
    elif crypto == "ethereum":
        alphabet = ETHEREUM_ALPHABET
        label = "Ethereum addresses use hexadecimal characters: 0-9 and a-f."
    else:
        alphabet = TOR_ALPHABET
        label = "Tor v3 onion addresses use Base32 characters: a-z and 2-7."

    invalid = sorted({character for character in normalized if character not in alphabet})
    if invalid:
        return False, f"{label} Invalid: {', '.join(invalid)}"
    return True, ""


def address_body(address: str, crypto: str) -> str:
    """Return the searchable part of an address, excluding fixed protocol text."""
    if crypto == "bitcoin" and address.startswith("1"):
        return address[1:]
    if crypto == "ethereum" and address.lower().startswith("0x"):
        return address[2:].lower()
    if crypto == "tor" and address.lower().endswith(".onion"):
        return address[:-6].lower()
    return address.lower() if crypto in {"ethereum", "tor"} else address


def matches_pattern(
    address: str,
    pattern: str,
    crypto: str,
    position: str,
    end_pattern: str = "",
) -> bool:
    """Return True when an address body matches the requested vanity pattern."""
    if position not in SUPPORTED_POSITIONS:
        raise ValueError(f"Unsupported pattern position: {position}")

    candidate = address_body(address, crypto)
    start = normalize_pattern(pattern, crypto)
    end = normalize_pattern(end_pattern, crypto)

    if position == "start":
        return candidate.startswith(start)
    if position == "end":
        return candidate.endswith(start)
    if position == "both":
        return bool(end) and candidate.startswith(start) and candidate.endswith(end)
    return start in candidate


def charset_size(crypto: str) -> int:
    if crypto == "bitcoin":
        return len(BITCOIN_ALPHABET)
    if crypto == "ethereum":
        return len(ETHEREUM_ALPHABET)
    if crypto == "tor":
        return len(TOR_ALPHABET)
    raise ValueError(f"Unsupported target: {crypto}")


def searchable_address_length(crypto: str) -> int:
    if crypto == "bitcoin":
        return 33
    if crypto == "ethereum":
        return 40
    if crypto == "tor":
        return 56
    raise ValueError(f"Unsupported target: {crypto}")


def estimate_difficulty(
    pattern: str,
    position: str,
    crypto: str,
    end_pattern: str = "",
) -> float:
    """Estimate the expected search space for a pattern."""
    normalized = normalize_pattern(pattern, crypto)
    if not normalized:
        return float("inf")

    size = charset_size(crypto)
    if position == "both":
        normalized_end = normalize_pattern(end_pattern, crypto)
        if not normalized_end:
            return float("inf")
        return float(size ** (len(normalized) + len(normalized_end)))

    if position == "anywhere":
        available_positions = max(1, searchable_address_length(crypto) - len(normalized) + 1)
        return float(size ** len(normalized)) / available_positions

    if position in {"start", "end"}:
        return float(size ** len(normalized))

    raise ValueError(f"Unsupported pattern position: {position}")
