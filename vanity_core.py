"""Shared validation, matching, and difficulty helpers for vanity searches."""

from __future__ import annotations

from typing import Tuple


BITCOIN_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ETHEREUM_ALPHABET = "0123456789abcdef"
TOR_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
SUPPORTED_CRYPTOS = {"bitcoin", "ethereum", "tor"}
SUPPORTED_POSITIONS = {"start", "end", "both", "anywhere"}

# Probability of each character occupying the FIRST searchable position of a
# Bitcoin P2PKH address body (the character right after the fixed leading
# "1"). This position is NOT uniform over Base58: the body encodes a 20-byte
# hash160 plus a 4-byte checksum, and its leading base-58 digits can only span
# a subset of the alphabet. Measured over 2,000,000 random addresses:
#   - "23456789ABCDEFGHJKLMNP": ~4.37% each (leading digits of 33-char bodies)
#   - "Q": ~1.51% (partial leading digit bucket)
#   - "1": ~0.39% (only when hash160 itself starts with a zero byte)
#   - remaining characters: ~0.074% each (shortened bodies only)
# Ignoring this made "start" searches beginning with e.g. T or z look ~24x
# easier than they really are, while patterns starting with 2-P looked ~2.5x
# harder than they are.
_BITCOIN_FIRST_CHAR_WEIGHTS = {
    **dict.fromkeys("23456789ABCDEFGHJKLMNP", 0.04375),
    "Q": 0.01515,
    "1": 0.00390,
    **dict.fromkeys("RSTUVWXYZabcdefghijkmnopqrstuvwxyz", 0.00074),
}
_BITCOIN_WEIGHT_TOTAL = sum(_BITCOIN_FIRST_CHAR_WEIGHTS.values())
BITCOIN_FIRST_CHAR_PROBABILITY = {
    character: weight / _BITCOIN_WEIGHT_TOTAL
    for character, weight in _BITCOIN_FIRST_CHAR_WEIGHTS.items()
}


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

    limit = searchable_address_length(crypto)
    if len(normalized) > limit:
        return False, (
            f"Pattern is too long: this target has at most {limit} searchable characters, "
            f"so a {len(normalized)}-character pattern can never be found."
        )
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


def _start_match_probability(pattern: str, crypto: str) -> float:
    """Probability that one random candidate matches `pattern` at the start."""
    size = charset_size(crypto)
    if crypto == "bitcoin":
        first = BITCOIN_FIRST_CHAR_PROBABILITY.get(pattern[0], 1 / size)
        return first * size ** (1 - len(pattern))
    return float(size) ** -len(pattern)


def estimate_difficulty(
    pattern: str,
    position: str,
    crypto: str,
    end_pattern: str = "",
) -> float:
    """Estimate the expected number of candidates per match for a pattern.

    Returns the reciprocal of the single-candidate match probability, i.e. the
    geometric distribution's mean. For Bitcoin "start" (and therefore
    "both"/"anywhere") patterns, the real, non-uniform first-character
    distribution of P2PKH bodies is taken into account.
    """
    normalized = normalize_pattern(pattern, crypto)
    if not normalized:
        return float("inf")

    size = charset_size(crypto)

    if position == "both":
        normalized_end = normalize_pattern(end_pattern, crypto)
        if not normalized_end:
            return float("inf")
        probability = _start_match_probability(normalized, crypto) * float(size) ** -len(normalized_end)
        return 1.0 / probability

    if position == "start":
        return 1.0 / _start_match_probability(normalized, crypto)

    if position == "end":
        return float(size ** len(normalized))

    if position == "anywhere":
        available_positions = max(1, searchable_address_length(crypto) - len(normalized) + 1)
        # Only the window aligned at offset 0 sees the non-uniform Bitcoin
        # leading character; the remaining windows stay uniform.
        first_window = _start_match_probability(normalized, crypto)
        other_windows = (available_positions - 1) * float(size) ** -len(normalized)
        return 1.0 / min(1.0, first_window + other_windows)

    raise ValueError(f"Unsupported pattern position: {position}")
