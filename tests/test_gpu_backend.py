import unittest

from gpu_backend import GPUAddressMatcher, list_gpu_devices
from vanity_core import matches_pattern


class GPUBackendTests(unittest.TestCase):
    def test_device_discovery_returns_a_list(self):
        self.assertIsInstance(list_gpu_devices(), list)

    def test_gpu_matcher_matches_cpu_rules_when_available(self):
        devices = list_gpu_devices()
        if not devices:
            self.skipTest("No OpenCL GPU device available.")

        addresses = [
            "1AbcDefGhijk",
            "1xyzDefGhijk",
            "1Abc000Ghijk",
            "1nomatch",
        ]
        matcher = GPUAddressMatcher(devices[0].key)
        gpu_indices = matcher.match_addresses(addresses, "Abc", "bitcoin", "start")
        cpu_indices = [
            index
            for index, address in enumerate(addresses)
            if matches_pattern(address, "Abc", "bitcoin", "start")
        ]

        self.assertEqual(cpu_indices, gpu_indices)

    def test_gpu_matcher_supports_anywhere_and_both_when_available(self):
        devices = list_gpu_devices()
        if not devices:
            self.skipTest("No OpenCL GPU device available.")

        matcher = GPUAddressMatcher(devices[0].key)
        eth_addresses = [
            "0xabc0000000000000000000000000000000000def",
            "0x0000000000000000000000000000000000000def",
            "0xabc000000000000000000000000000000000000",
        ]

        self.assertEqual([0], matcher.match_addresses(eth_addresses, "abc", "ethereum", "both", "def"))
        self.assertEqual([0, 2], matcher.match_addresses(eth_addresses, "abc", "ethereum", "anywhere"))


if __name__ == "__main__":
    unittest.main()
