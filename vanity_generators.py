"""
Address generators for Bitcoin, Ethereum, and Tor onion services.

The generators are offline, CPU-only, and return each address together with
the private key material needed to recreate it.
"""

import base64
import hashlib
import secrets
from typing import Tuple

import base58
from Crypto.Hash import keccak
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

try:
    from coincurve import PrivateKey as CoincurvePrivateKey
except Exception:  # pragma: no cover - optional performance dependency.
    CoincurvePrivateKey = None


SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
BITCOIN_MAINNET_P2PKH_VERSION = b"\x00"
BITCOIN_MAINNET_WIF_VERSION = b"\x80"
ONION_V3_CHECKSUM_PREFIX = b".onion checksum"
ONION_V3_VERSION = b"\x03"


def _random_secp256k1_private_value() -> int:
    """Return a uniformly distributed valid secp256k1 private key value."""
    return secrets.randbelow(SECP256K1_ORDER - 1) + 1


def _double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


try:
    hashlib.new("ripemd160", b"").digest()

    def _ripemd160(data: bytes) -> bytes:
        return hashlib.new("ripemd160", data).digest()
except Exception:  # pragma: no cover - OpenSSL 3.x without the legacy provider.
    from Crypto.Hash import RIPEMD160 as _CryptoRIPEMD160

    def _ripemd160(data: bytes) -> bytes:
        return _CryptoRIPEMD160.new(data).digest()


def _hash160(data: bytes) -> bytes:
    return _ripemd160(hashlib.sha256(data).digest())


def _base58check_encode(payload: bytes) -> str:
    checksum = _double_sha256(payload)[:4]
    return base58.b58encode(payload + checksum).decode("ascii")


def keccak256(data: bytes) -> bytes:
    """Return Ethereum's Keccak-256 digest."""
    digest = keccak.new(digest_bits=256)
    digest.update(data)
    return digest.digest()


def _secp256k1_public_key(private_value: int, private_key_bytes: bytes, compressed: bool) -> bytes:
    if CoincurvePrivateKey is not None:
        return CoincurvePrivateKey(private_key_bytes).public_key.format(compressed=compressed)

    private_key = ec.derive_private_key(private_value, ec.SECP256K1())
    public_format = PublicFormat.CompressedPoint if compressed else PublicFormat.UncompressedPoint
    return private_key.public_key().public_bytes(Encoding.X962, public_format)


class BitcoinGenerator:
    """
    Generate Bitcoin mainnet P2PKH addresses.

    Uncompressed keys return WIF values starting with "5". Compressed keys
    return WIF values starting with "K" or "L".

    For hot search loops, use ``generate_candidate`` (which skips WIF
    encoding) and only call ``finalize_match`` for confirmed matches. The
    ``generate_address`` convenience method returns identical results by
    combining both steps.
    """

    def generate_candidate(self, compressed: bool = False) -> Tuple[str, Tuple[bytes, bool]]:
        """Return an address plus raw private key material for later finalization."""
        private_value = _random_secp256k1_private_value()
        private_key_bytes = private_value.to_bytes(32, "big")
        public_key_bytes = _secp256k1_public_key(private_value, private_key_bytes, compressed)

        address_payload = BITCOIN_MAINNET_P2PKH_VERSION + _hash160(public_key_bytes)
        return _base58check_encode(address_payload), (private_key_bytes, compressed)

    @staticmethod
    def finalize_match(address: str, material: Tuple[bytes, bool]) -> Tuple[str, str]:
        """Return the displayable address and the WIF private key for a match."""
        private_key_bytes, compressed = material
        payload = BITCOIN_MAINNET_WIF_VERSION + private_key_bytes
        if compressed:
            payload += b"\x01"
        return address, _base58check_encode(payload)

    def generate_address(self, compressed: bool = False) -> Tuple[str, str]:
        address, material = self.generate_candidate(compressed)
        return self.finalize_match(address, material)


class EthereumGenerator:
    """
    Generate Ethereum externally owned account addresses.

    The address is returned in EIP-55 checksum form. Pattern matching elsewhere
    is case-insensitive, so checksum casing does not make vanity searches harder.
    """

    @staticmethod
    def checksum_address(address_hex: str) -> str:
        lowercase = address_hex.lower()
        checksum_hash = keccak256(lowercase.encode("ascii")).hex()
        checksummed = "".join(
            character.upper() if int(checksum_hash[index], 16) >= 8 else character
            for index, character in enumerate(lowercase)
        )
        return "0x" + checksummed

    def generate_candidate(self) -> Tuple[str, bytes]:
        """Return a lowercase address candidate plus raw private key bytes.

        The EIP-55 checksum casing is intentionally deferred to
        ``finalize_match`` because pattern matching is case-insensitive and
        computing it for every attempt would waste one Keccak-256 hash per
        candidate.
        """
        private_value = _random_secp256k1_private_value()
        private_key_bytes = private_value.to_bytes(32, "big")
        public_key_bytes = _secp256k1_public_key(private_value, private_key_bytes, compressed=False)[1:]
        address_hex = keccak256(public_key_bytes)[-20:].hex()
        return "0x" + address_hex, private_key_bytes

    @staticmethod
    def finalize_match(address: str, material: bytes) -> Tuple[str, str]:
        """Return the EIP-55 checksummed address and hex private key for a match."""
        if not address.lower().startswith("0x") or len(address) != 42:
            raise ValueError("Ethereum finalize_match expects a 40-character lowercase hex address.")
        return EthereumGenerator.checksum_address(address[2:]), "0x" + material.hex()

    def generate_address(self) -> Tuple[str, str]:
        address, material = self.generate_candidate()
        return self.finalize_match(address, material)


class TorGenerator:
    """
    Generate Tor v3 onion addresses from Ed25519 keys.

    The returned private key is a PKCS#8 PEM Ed25519 key. It can be loaded by
    standard cryptography tooling to recreate the public key and onion address.

    For hot search loops, use ``generate_candidate`` (which skips PEM
    serialization) and only call ``finalize_match`` for confirmed matches.
    """

    def generate_candidate(self) -> Tuple[str, bytes]:
        """Return an onion address plus the raw 32-byte Ed25519 private seed."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        private_key_bytes = private_key.private_bytes(
            Encoding.Raw,
            PrivateFormat.Raw,
            NoEncryption(),
        )
        public_key_bytes = private_key.public_key().public_bytes(
            Encoding.Raw,
            PublicFormat.Raw,
        )
        return self.onion_v3_address(public_key_bytes), private_key_bytes

    @staticmethod
    def finalize_match(address: str, material: bytes) -> Tuple[str, str]:
        """Return the onion address and PKCS#8 PEM private key for a match."""
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(material)
        private_key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption(),
        ).decode("ascii").strip()
        return address, private_key_pem

    def generate_address(self) -> Tuple[str, str]:
        address, material = self.generate_candidate()
        return self.finalize_match(address, material)

    @staticmethod
    def onion_v3_address(public_key_bytes: bytes) -> str:
        if len(public_key_bytes) != 32:
            raise ValueError("Tor v3 onion addresses require a 32-byte Ed25519 public key.")

        checksum = hashlib.sha3_256(
            ONION_V3_CHECKSUM_PREFIX + public_key_bytes + ONION_V3_VERSION
        ).digest()[:2]
        address_bytes = public_key_bytes + checksum + ONION_V3_VERSION
        return base64.b32encode(address_bytes).decode("ascii").rstrip("=").lower() + ".onion"
