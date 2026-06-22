# Vanity Address Generator

An offline vanity address generator for Bitcoin, Ethereum, and Tor v3 onion addresses, with CPU and OpenCL GPU-assisted search modes.

![Vanity Address Generator](screen/Screen1.png)

## Features

- Bitcoin mainnet P2PKH address generation.
- Optional compressed Bitcoin public keys with matching WIF private keys.
- Ethereum address generation with Keccak-256 and EIP-55 checksum casing.
- Tor v3 onion address generation from Ed25519 keys.
- Start, end, both, and anywhere pattern matching.
- Worker-based generation with live speed, attempt, and result counters.
- Optional OpenCL GPU-assisted batch matching with device selection.
- Fast secp256k1 public key derivation through `coincurve` when available.
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

Install optional secp256k1 acceleration with:

```bash
python -m pip install -r requirements-speed.txt
```

Install optional GPU dependencies with:

```bash
python -m pip install -r requirements-gpu.txt
```

GPU mode also requires a working OpenCL runtime and GPU driver. NVIDIA, AMD, and Intel GPU OpenCL runtimes are supported when exposed through `pyopencl`.

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

## GPU Mode

The application includes a CPU/GPU compute selector. CPU mode is always available. GPU mode appears when at least one OpenCL GPU device is detected.

GPU mode uses OpenCL to filter generated address batches against the selected vanity pattern. Cryptographic key generation and address derivation remain standards-compliant and are verified by tests. This keeps private key handling simple and portable while still using the GPU for high-volume pattern checks.

Notes:

- Install `requirements-gpu.txt` to enable OpenCL support.
- Keep `requirements.txt` installed even when using GPU mode.
- Select the target GPU from the GUI before starting a search.
- If OpenCL initialization fails, the GUI reports the error before launching workers.
- For very short patterns, CPU mode can still be faster because GPU transfer overhead may dominate.

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
- OpenCL GPU matcher parity with CPU matching rules when a GPU is available.

## Performance Notes

Vanity search is probabilistic. Each extra required character multiplies the expected work by the target alphabet size:

| Pattern length | Bitcoin | Ethereum | Tor v3 onion |
| --- | ---: | ---: | ---: |
| 3 | about 195,000 attempts | about 4,000 attempts | about 33,000 attempts |
| 4 | about 11 million attempts | about 65,000 attempts | about 1 million attempts |
| 5 | about 656 million attempts | about 1 million attempts | about 34 million attempts |

Use a worker count close to the CPU core count for the best balance of throughput and system responsiveness. GPU mode processes candidates in batches of 4,096 addresses per worker. Very long patterns can take hours, days, or longer.

## Project Layout

```text
main.py                Tkinter GUI and worker orchestration
gpu_backend.py         Optional OpenCL GPU matcher and device discovery
vanity_generators.py   Bitcoin, Ethereum, and Tor key/address generators
vanity_core.py         Pattern validation, matching, and difficulty helpers
tests/                 Address and matching verification tests
requirements.txt       Python dependencies
requirements-speed.txt Optional secp256k1 acceleration dependency
requirements-gpu.txt   Optional OpenCL GPU dependencies
```

## Legal Disclaimer

This software is provided for educational and legitimate personal use only. Do not use it to attack, impersonate, or compromise addresses, services, or identities that you do not own. You are responsible for complying with applicable laws and for protecting any generated private keys.

## License

This project is released under the MIT License. See `LICENSE` for details.
