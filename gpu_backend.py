"""Optional OpenCL helpers for GPU-assisted vanity matching."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from vanity_core import address_body, normalize_pattern


GPU_MATCH_KERNEL = r"""
__kernel void match_address_bodies(
    __global const uchar *bodies,
    __global const int *lengths,
    const int width,
    __global const uchar *pattern,
    const int pattern_len,
    __global const uchar *end_pattern,
    const int end_pattern_len,
    const int position,
    __global uchar *matches
) {
    int gid = get_global_id(0);
    int len = lengths[gid];
    __global const uchar *body = bodies + (gid * width);
    uchar ok = 0;

    if (position == 0) {
        if (pattern_len <= len) {
            ok = 1;
            for (int i = 0; i < pattern_len; i++) {
                if (body[i] != pattern[i]) {
                    ok = 0;
                    break;
                }
            }
        }
    } else if (position == 1) {
        if (pattern_len <= len) {
            int start = len - pattern_len;
            ok = 1;
            for (int i = 0; i < pattern_len; i++) {
                if (body[start + i] != pattern[i]) {
                    ok = 0;
                    break;
                }
            }
        }
    } else if (position == 2) {
        if (pattern_len <= len && end_pattern_len > 0 && end_pattern_len <= len) {
            ok = 1;
            for (int i = 0; i < pattern_len; i++) {
                if (body[i] != pattern[i]) {
                    ok = 0;
                    break;
                }
            }
            if (ok) {
                int end_start = len - end_pattern_len;
                for (int i = 0; i < end_pattern_len; i++) {
                    if (body[end_start + i] != end_pattern[i]) {
                        ok = 0;
                        break;
                    }
                }
            }
        }
    } else {
        if (pattern_len <= len) {
            for (int start = 0; start <= len - pattern_len; start++) {
                uchar found = 1;
                for (int i = 0; i < pattern_len; i++) {
                    if (body[start + i] != pattern[i]) {
                        found = 0;
                        break;
                    }
                }
                if (found) {
                    ok = 1;
                    break;
                }
            }
        }
    }

    matches[gid] = ok;
}
"""


POSITION_CODES = {
    "start": 0,
    "end": 1,
    "both": 2,
    "anywhere": 3,
}


@dataclass(frozen=True)
class GpuDevice:
    platform_index: int
    device_index: int
    platform_name: str
    name: str
    vendor: str
    compute_units: int

    @property
    def key(self) -> str:
        return f"{self.platform_index}:{self.device_index}"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.vendor}, {self.compute_units} CUs)"


def _load_opencl():
    os.environ.setdefault("PYOPENCL_NO_CACHE", "1")
    try:
        import numpy as np
        import pyopencl as cl
    except Exception as exc:  # pragma: no cover - depends on optional runtime.
        raise RuntimeError(f"OpenCL GPU support is unavailable: {exc}") from exc
    return cl, np


def list_gpu_devices() -> List[GpuDevice]:
    try:
        cl, _np = _load_opencl()
    except RuntimeError:
        return []

    devices: list[GpuDevice] = []
    try:
        platforms = cl.get_platforms()
    except Exception:
        return []

    for platform_index, platform in enumerate(platforms):
        try:
            platform_devices = platform.get_devices(device_type=cl.device_type.GPU)
        except Exception:
            continue

        for device_index, device in enumerate(platform_devices):
            devices.append(
                GpuDevice(
                    platform_index=platform_index,
                    device_index=device_index,
                    platform_name=platform.name,
                    name=device.name.strip(),
                    vendor=device.vendor.strip(),
                    compute_units=int(device.max_compute_units),
                )
            )
    return devices


class GPUAddressMatcher:
    """Batch pattern matcher backed by an OpenCL GPU device."""

    def __init__(self, device_key: str | None = None):
        self.cl, self.np = _load_opencl()
        self.device = self._select_device(device_key)
        self.context = self.cl.Context([self.device])
        self.queue = self.cl.CommandQueue(self.context)
        self.program = self.cl.Program(self.context, GPU_MATCH_KERNEL).build()
        self.kernel = self.cl.Kernel(self.program, "match_address_bodies")

    @property
    def device_label(self) -> str:
        return f"{self.device.name.strip()} ({self.device.vendor.strip()})"

    def _select_device(self, device_key: str | None):
        platforms = self.cl.get_platforms()
        if device_key:
            platform_index_text, device_index_text = device_key.split(":", 1)
            platform_index = int(platform_index_text)
            device_index = int(device_index_text)
            return platforms[platform_index].get_devices(device_type=self.cl.device_type.GPU)[device_index]

        for platform in platforms:
            devices = platform.get_devices(device_type=self.cl.device_type.GPU)
            if devices:
                return devices[0]
        raise RuntimeError("No OpenCL GPU device was found.")

    def match_addresses(
        self,
        addresses: list[str],
        pattern: str,
        crypto: str,
        position: str,
        end_pattern: str = "",
    ) -> list[int]:
        if not addresses:
            return []

        bodies = [address_body(address, crypto).encode("ascii") for address in addresses]
        width = max(1, max(len(body) for body in bodies))
        body_matrix = self.np.zeros((len(bodies), width), dtype=self.np.uint8)
        lengths = self.np.zeros(len(bodies), dtype=self.np.int32)

        for index, body in enumerate(bodies):
            body_matrix[index, : len(body)] = self.np.frombuffer(body, dtype=self.np.uint8)
            lengths[index] = len(body)

        pattern_bytes = normalize_pattern(pattern, crypto).encode("ascii")
        end_pattern_bytes = normalize_pattern(end_pattern, crypto).encode("ascii")
        pattern_array = self.np.frombuffer(pattern_bytes or b"\x00", dtype=self.np.uint8).copy()
        end_pattern_array = self.np.frombuffer(end_pattern_bytes or b"\x00", dtype=self.np.uint8).copy()
        matches = self.np.zeros(len(bodies), dtype=self.np.uint8)

        flags = self.cl.mem_flags
        body_buffer = self.cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=body_matrix)
        length_buffer = self.cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=lengths)
        pattern_buffer = self.cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=pattern_array)
        end_pattern_buffer = self.cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=end_pattern_array)
        match_buffer = self.cl.Buffer(self.context, flags.WRITE_ONLY, matches.nbytes)

        self.kernel(
            self.queue,
            (len(bodies),),
            None,
            body_buffer,
            length_buffer,
            self.np.int32(width),
            pattern_buffer,
            self.np.int32(len(pattern_bytes)),
            end_pattern_buffer,
            self.np.int32(len(end_pattern_bytes)),
            self.np.int32(POSITION_CODES[position]),
            match_buffer,
        )
        self.cl.enqueue_copy(self.queue, matches, match_buffer)
        self.queue.finish()
        return [index for index, matched in enumerate(matches) if matched]
