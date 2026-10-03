import unittest
from pathlib import Path

from generate_edid import checksum, patch, sanitize_identity

ROOT = Path(__file__).resolve().parent


class EdidTests(unittest.TestCase):
    def setUp(self):
        self.native = (ROOT / "g60sd-hdmi-native-sanitized.bin").read_bytes()
        self.generated = patch(self.native)

    def test_reproducible_binary(self):
        self.assertEqual(self.generated, (ROOT / "g60sd-hdmi.bin").read_bytes())
        self.assertEqual(len(self.generated), 512)

    def test_checksums(self):
        for offset in range(0, len(self.generated), 128):
            self.assertEqual(sum(self.generated[offset:offset + 128]) % 256, 0)
        extension = self.generated[384:512]
        self.assertEqual(sum(extension[1:6 + extension[2]]) % 256, 0)

    def test_only_intended_native_changes(self):
        changes = {i for i, (a, b) in enumerate(zip(self.native, self.generated)) if a != b}
        self.assertEqual(changes, {134, 174, 255})
        self.assertEqual(self.generated[174], 0xC1)
        self.assertEqual(self.generated[134], 3)
        self.assertEqual(self.generated[126], 1)

    def test_native_timings_are_copied_exactly(self):
        extension = self.generated[384:512]
        self.assertEqual(extension[:5], bytes([0x70, 0x12, 98, 3, 0]))
        self.assertEqual(extension[20:23], bytes([3, 1, 80]))
        for source, destination in ((263, 43), (286, 63), (309, 83)):
            original = self.native[source:source + 20]
            copied = extension[destination:destination + 20]
            self.assertEqual(copied[3:], original[3:])
            self.assertEqual((int.from_bytes(copied[:3], "little") + 1) * 10,
                             int.from_bytes(original[:3], "little") + 1)
        self.assertTrue(extension[26] & 0x80)  # 120 Hz preferred descriptor.

    def test_public_files_have_no_serial_fields(self):
        for blob in (self.native, self.generated):
            self.assertEqual(blob[12:16], bytes(4))
            for offset in range(54, 126, 18):
                descriptor = blob[offset:offset + 18]
                self.assertFalse(descriptor[:3] == bytes(3) and descriptor[3] == 0xFF)

    def test_generator_sanitizes_raw_identity(self):
        private = bytearray(self.native)
        private[12:16] = bytes.fromhex("12345678")
        private[108:126] = bytes([0, 0, 0, 0xFF, 0]) + b"PRIVATE-ID\n  "
        base = private[:128]
        checksum(base)
        private[:128] = base
        self.assertEqual(sanitize_identity(private), self.native)
        self.assertEqual(patch(private), self.generated)
        self.assertNotIn(b"PRIVATE-ID", self.generated)

    def test_invalid_input_is_rejected(self):
        corrupt = bytearray(self.native)
        corrupt[200] ^= 1
        for invalid in (self.native[:-1], bytes(384), corrupt):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(ValueError):
                    patch(invalid)


if __name__ == "__main__":
    unittest.main()
