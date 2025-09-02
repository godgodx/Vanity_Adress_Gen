"""
Vanity Address Generators for Bitcoin, Ethereum, and Tor
CPU-only offline generators using standard cryptographic libraries
"""

import hashlib
import secrets
import base58
import struct
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from Crypto.Hash import keccak


class BitcoinGenerator:
    """
    Bitcoin vanity address generator
    Generates P2PKH (Pay-to-Public-Key-Hash) addresses starting with '1'
    Compatible with all major Bitcoin wallets
    """
    
    def __init__(self):
        self.version_byte = b'\x00'  # Mainnet P2PKH version
    
    def generate_address(self, compressed: bool = False) -> Tuple[str, str]:
        """
        Generate a Bitcoin address and its corresponding private key
        Args:
            compressed: If True, generate compressed public key and address
        Returns: (address, private_key_wif)
        """
        # Generate valid private key (avoid recursion)
        secp256k1_order = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        
        while True:
            # Generate random private key (32 bytes)
            private_key_bytes = secrets.token_bytes(32)
            private_key_int = int.from_bytes(private_key_bytes, 'big')
            
            # Check if valid (not zero and less than secp256k1 order)
            if private_key_int != 0 and private_key_int < secp256k1_order:
                break
        
        # Create public key from private key using secp256k1
        private_key = ec.derive_private_key(private_key_int, ec.SECP256K1())
        public_key = private_key.public_key()
        
        if compressed:
            # Get compressed public key bytes
            x = public_key.public_numbers().x.to_bytes(32, 'big')
            y = public_key.public_numbers().y
            # Compressed: 02 if y is even, 03 if y is odd
            prefix = b'\x02' if y % 2 == 0 else b'\x03'
            public_key_full = prefix + x
        else:
            # Get uncompressed public key bytes
            public_key_bytes = public_key.public_numbers().x.to_bytes(32, 'big') + \
                              public_key.public_numbers().y.to_bytes(32, 'big')
            public_key_full = b'\x04' + public_key_bytes
        
        # Hash the public key (SHA256 then RIPEMD160)
        sha256_hash = hashlib.sha256(public_key_full).digest()
        ripemd160_hash = hashlib.new('ripemd160', sha256_hash).digest()
        
        # Add version byte
        versioned_hash = self.version_byte + ripemd160_hash
        
        # Calculate checksum (double SHA256)
        checksum = hashlib.sha256(hashlib.sha256(versioned_hash).digest()).digest()[:4]
        
        # Create final address
        address_bytes = versioned_hash + checksum
        address = base58.b58encode(address_bytes).decode('utf-8')
        
        # Create WIF private key (Wallet Import Format)
        private_key_wif = self._create_wif(private_key_bytes, compressed)
        
        return address, private_key_wif
    
    def _create_wif(self, private_key_bytes: bytes, compressed: bool = False) -> str:
        """Create Wallet Import Format (WIF) private key"""
        # Add version byte for mainnet (0x80)
        extended_key = b'\x80' + private_key_bytes
        
        if compressed:
            # Add compression flag for compressed keys (starts with "K" or "L")
            extended_key += b'\x01'
        # Uncompressed keys have NO compression flag (starts with "5")
        
        # Add checksum (double SHA256 of extended key)
        checksum = hashlib.sha256(hashlib.sha256(extended_key).digest()).digest()[:4]
        wif_bytes = extended_key + checksum
        
        return base58.b58encode(wif_bytes).decode('utf-8')


class EthereumGenerator:
    """
    Ethereum vanity address generator with proper Keccak-256 hashing
    Generates standard Ethereum addresses following the official specification
    Compatible with MetaMask and other Ethereum wallets
    """
    
    def keccak256(self, data: bytes) -> bytes:
        """
        Compute Keccak-256 hash (the real one used by Ethereum)
        """
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()
    
    def generate_address(self) -> Tuple[str, str]:
        """
        Generate an Ethereum address and its corresponding private key
        Returns: (address, private_key_hex_with_0x)
        """
        # Generate valid private key (avoid recursion)
        secp256k1_order = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        
        while True:
            # Generate random private key (32 bytes)
            private_key_bytes = secrets.token_bytes(32)
            private_key_int = int.from_bytes(private_key_bytes, 'big')
            
            # Check if valid (not zero and less than secp256k1 order)
            if private_key_int != 0 and private_key_int < secp256k1_order:
                break
        
        # Create public key from private key using secp256k1
        private_key = ec.derive_private_key(private_key_int, ec.SECP256K1())
        public_key = private_key.public_key()
        
        # Get uncompressed public key bytes (64 bytes: 32 bytes x + 32 bytes y)
        public_key_bytes = public_key.public_numbers().x.to_bytes(32, 'big') + \
                          public_key.public_numbers().y.to_bytes(32, 'big')
        
        # Apply Keccak-256 to the public key (this is the official Ethereum method)
        keccak_hash = self.keccak256(public_key_bytes)
        
        # Take last 20 bytes for Ethereum address
        address_bytes = keccak_hash[-20:]
        
        # Convert to hex string and add 0x prefix
        address_hex = address_bytes.hex().lower()
        address = '0x' + address_hex
        
        # Private key as hex string with 0x prefix (MetaMask format)
        private_key_hex = '0x' + private_key_bytes.hex().lower()
        
        return address, private_key_hex

class TorGenerator:
    """
    Tor .onion v3 vanity address generator (modern format)
    Generates 56-character .onion v3 addresses with Ed25519 keys
    Compatible with modern Tor network (v2 deprecated since 2021)
    """
    
    def generate_address(self) -> Tuple[str, str]:
        """
        Generate a Tor .onion v3 address and its corresponding private key
        Returns: (onion_v3_address, ed25519_private_key)
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization
            
            # Generate Ed25519 private key for v3 onion addresses
            private_key = ed25519.Ed25519PrivateKey.generate()
            
            # Get public key
            public_key = private_key.public_key()
            
            # Get raw public key bytes (32 bytes for Ed25519)
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Calculate onion v3 address from public key
            # v3 onion address = base32(public_key + checksum + version)[0:56] + ".onion"
            
            # Add version byte (0x03 for v3)
            version = b'\x03'
            
            # Calculate checksum: SHA3-256(".onion checksum" + public_key + version)[:2]
            checksum_input = b".onion checksum" + public_key_bytes + version
            checksum = hashlib.sha3_256(checksum_input).digest()[:2]
            
            # Combine: public_key + checksum + version
            address_bytes = public_key_bytes + checksum + version
            
            # Encode with base32 and take first 56 characters
            onion_address = base32_encode_v3(address_bytes)[:56] + '.onion'
            
            # Serialize private key in a format usable with Tor
            # For Tor v3, we need the raw 32-byte seed
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Format as hex for easy use (Tor v3 format)
            private_key_hex = private_key_bytes.hex().upper()
            
            # Create Tor-compatible key format
            tor_private_key = f"""== ed25519v1-secret: type0 ==
{private_key_hex}
== ed25519v1-public: type0 ==
{public_key_bytes.hex().upper()}"""
            
            return onion_address, tor_private_key
            
        except ImportError as e:
            raise RuntimeError("Ed25519 is required for Tor v3. Install 'cryptography' package with Ed25519 support.") from e
            
# Base32 encoding for Tor addresses
def base32_encode(data):
    """Convert data to base32 encoding for .onion v2 addresses (deprecated)"""
    import base64
    # Use base32 encoding for Tor addresses
    encoded = base64.b32encode(data).decode('ascii')
    # Remove padding and make lowercase for .onion format
    return encoded.rstrip('=').lower()

def base32_encode_v3(data):
    """Convert data to base32 encoding for .onion v3 addresses (modern)"""
    import base64
    # Use base32 encoding for Tor v3 addresses
    encoded = base64.b32encode(data).decode('ascii')
    # Remove padding and make lowercase for .onion v3 format
    return encoded.rstrip('=').lower()
