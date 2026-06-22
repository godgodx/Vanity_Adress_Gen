# Vanity Address Generator

An offline CPU-based vanity address generator for Bitcoin, Ethereum, and Tor v3 onion addresses.

![Vanity Address Generator](screen/Screen1.png)

## Features

- Bitcoin mainnet P2PKH address generation.
- Optional compressed Bitcoin public keys with matching WIF private keys.
- Ethereum address generation with Keccak-256 and EIP-55 checksum casing.
- Tor v3 onion address generation from Ed25519 keys.
- Start, end, both, and anywhere pattern matching.
- Worker-based generation with live speed, attempt, and result counters.
- Per-run output files under `output/`.

## Security Notice

This project generates real private keys. Anyone with a generated private key can control the associated funds or service identity. Run the tool offline when possible, keep output files private, and test with small amounts before using any generated cryptocurrency address.

## Requirements

- Python 3.10 or newer.
- `cryptography`
- `pycryptodome`
- `base58`
- `tkinter` for the GUI, usually bundled with desktop Python installs.

Install Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

Linux users may need to install tkinter separately:

```bash
sudo apt-get install python3-tk
```

## Running

Windows:

```cmd
start.bat
```

Linux or macOS:

```bash
chmod +x start.sh
./start.sh
```

Manual launch:

```bash
python main.py
```

## Pattern Rules

Patterns are matched against the searchable address body, not fixed protocol text:

- Bitcoin P2PKH addresses always start with `1`; search ignores that fixed leading prefix.
- Ethereum addresses always start with `0x`; search ignores that fixed leading prefix.
- Tor v3 onion addresses always end with `.onion`; search ignores that fixed suffix.

Allowed pattern characters:

| Target | Alphabet |
| --- | --- |
| Bitcoin | Base58: `1-9`, `A-Z`, `a-z`, excluding `0`, `O`, `I`, `l` |
| Ethereum | Hexadecimal: `0-9`, `a-f` |
| Tor v3 onion | Base32: `a-z`, `2-7` |

Bitcoin matching is case-sensitive. Ethereum and Tor matching are case-insensitive.

## Output

Each run writes matches to a timestamped file:

```text
output/{target}_vanity_{pattern}_{timestamp}.txt
```

Private key formats:

| Target | Private key output |
| --- | --- |
| Bitcoin | WIF. Uncompressed keys start with `5`; compressed keys start with `K` or `L`. |
| Ethereum | Hex private key with `0x` prefix. |
| Tor v3 onion | PKCS#8 PEM Ed25519 private key. |

## Verification

The test suite validates that generated addresses can be recomputed from the returned private keys:

```bash
python -m unittest discover -s tests
```

The tests cover:

- Bitcoin Base58Check address and WIF consistency.
- Bitcoin compressed and uncompressed public key modes.
- Ethereum Keccak-256 address derivation and EIP-55 checksum casing.
- Tor v3 onion checksum and Ed25519 public key derivation.
- Pattern validation and matching rules.

## Performance Notes

Vanity search is probabilistic. Each extra required character multiplies the expected work by the target alphabet size:

| Pattern length | Bitcoin | Ethereum | Tor v3 onion |
| --- | ---: | ---: | ---: |
| 3 | about 195,000 attempts | about 4,000 attempts | about 33,000 attempts |
| 4 | about 11 million attempts | about 65,000 attempts | about 1 million attempts |
| 5 | about 656 million attempts | about 1 million attempts | about 34 million attempts |

Use a worker count close to the CPU core count for the best balance of throughput and system responsiveness. Very long patterns can take hours, days, or longer.

## Project Layout

```text
main.py                Tkinter GUI and worker orchestration
vanity_generators.py   Bitcoin, Ethereum, and Tor key/address generators
vanity_core.py         Pattern validation, matching, and difficulty helpers
tests/                 Address and matching verification tests
requirements.txt       Python dependencies
```

## Legal Disclaimer

This software is provided for educational and legitimate personal use only. Do not use it to attack, impersonate, or compromise addresses, services, or identities that you do not own. You are responsible for complying with applicable laws and for protecting any generated private keys.

## License

This project is released under the MIT License. See `LICENSE` for details.
