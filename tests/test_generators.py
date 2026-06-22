import base64
import hashlib
import re
import unittest

import base58
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import ec

from vanity_generators import BitcoinGenerator, EthereumGenerator, TorGenerator, keccak256


SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash160(data: bytes) -> bytes:
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def base58check_decode(value: str) -> bytes:
    raw = base58.b58decode(value)
    payload, checksum = raw[:-4], raw[-4:]
    if double_sha256(payload)[:4] != checksum:
        raise AssertionError("Invalid Base58Check checksum.")
    return payload


def bitcoin_address_from_wif(wif: str, compressed: bool) -> str:
    payload = base58check_decode(wif)
    assert payload[0] == 0x80

    if compressed:
        assert len(payload) == 34
        assert payload[-1] == 0x01
        private_key_bytes = payload[1:-1]
        public_format = PublicFormat.CompressedPoint
    else:
        assert len(payload) == 33
        private_key_bytes = payload[1:]
        public_format = PublicFormat.UncompressedPoint

    private_value = int.from_bytes(private_key_bytes, "big")
    assert 0 < private_value < SECP256K1_ORDER
    private_key = ec.derive_private_key(private_value, ec.SECP256K1())
    public_key_bytes = private_key.public_key().public_bytes(Encoding.X962, public_format)
    address_payload = b"\x00" + hash160(public_key_bytes)
    return base58.b58encode(address_payload + double_sha256(address_payload)[:4]).decode("ascii")


class BitcoinGeneratorTests(unittest.TestCase):
    def test_uncompressed_address_matches_wif_private_key(self):
        address, wif = BitcoinGenerator().generate_address(compressed=False)

        self.assertTrue(address.startswith("1"))
        self.assertTrue(wif.startswith("5"))
        self.assertEqual(address, bitcoin_address_from_wif(wif, compressed=False))

    def test_compressed_address_matches_wif_private_key(self):
        address, wif = BitcoinGenerator().generate_address(compressed=True)

        self.assertTrue(address.startswith("1"))
        self.assertIn(wif[0], {"K", "L"})
        self.assertEqual(address, bitcoin_address_from_wif(wif, compressed=True))


class EthereumGeneratorTests(unittest.TestCase):
    def test_address_matches_private_key_and_checksum(self):
        address, private_key_hex = EthereumGenerator().generate_address()

        self.assertRegex(address, r"^0x[0-9a-fA-F]{40}$")
        self.assertRegex(private_key_hex, r"^0x[0-9a-f]{64}$")

        private_value = int(private_key_hex[2:], 16)
        self.assertGreater(private_value, 0)
        self.assertLess(private_value, SECP256K1_ORDER)

        private_key = ec.derive_private_key(private_value, ec.SECP256K1())
        public_key_bytes = private_key.public_key().public_bytes(
            Encoding.X962,
            PublicFormat.UncompressedPoint,
        )[1:]
        derived_hex = keccak256(public_key_bytes)[-20:].hex()

        self.assertEqual(address[2:].lower(), derived_hex)
        self.assertEqual(address, EthereumGenerator.checksum_address(derived_hex))


class TorGeneratorTests(unittest.TestCase):
    def test_onion_address_matches_private_key(self):
        address, private_key_pem = TorGenerator().generate_address()

        self.assertRegex(address, r"^[a-z2-7]{56}\.onion$")
        private_key = load_pem_private_key(private_key_pem.encode("ascii"), password=None)
        public_key_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        self.assertEqual(address, TorGenerator.onion_v3_address(public_key_bytes))

        decoded = base64.b32decode(address[:-6].upper())
        self.assertEqual(decoded[:32], public_key_bytes)
        self.assertEqual(decoded[34:], b"\x03")

        expected_checksum = hashlib.sha3_256(b".onion checksum" + public_key_bytes + b"\x03").digest()[:2]
        self.assertEqual(decoded[32:34], expected_checksum)


if __name__ == "__main__":
    unittest.main()
