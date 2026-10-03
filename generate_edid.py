"""Expose this G60SD's native CTA Type VII timings in standalone DisplayID 1.2.

Linux 7.2's add_displayid_detailed_modes walks standalone DisplayID extensions,
not the Type VII timing blocks embedded in CTA. Keep the native CTA data and
120 Hz preferred mode; duplicate the high-refresh timings without inventing any.
Hide 12-bit DSC to work around AMDGPU's equality-based bpc_supported conversion,
which otherwise enables 12-bit DSC but incorrectly disables 10-bit DSC.
Remove numeric and descriptor serial numbers before generating the public EDID.
"""

import sys
from pathlib import Path


def checksum(block):
    block[-1] = (-sum(block[:-1])) & 0xFF


def sanitize_identity(native):
    sanitized = bytearray(native)
    sanitized[12:16] = bytes(4)
    for offset in range(54, 126, 18):
        descriptor = sanitized[offset:offset + 18]
        if descriptor[:3] == bytes(3) and descriptor[3] == 0xFF:
            # Replace the serial descriptor with an EDID dummy descriptor.
            sanitized[offset:offset + 18] = bytes([0, 0, 0, 0x10]) + bytes(14)
    base = sanitized[:128]
    checksum(base)
    sanitized[:128] = base
    return bytes(sanitized)


def patch(native):
    if len(native) != 384 or native[:8] != bytes.fromhex("00ffffffffffff00"):
        raise ValueError("Expected the captured three-block G60SD HDMI EDID")
    if native[8:12] != bytes.fromhex("4c2dc275"):
        raise ValueError("Unexpected monitor manufacturer/product")
    if any(sum(native[i:i + 128]) % 256 for i in range(0, len(native), 128)):
        raise ValueError("Invalid native EDID checksum")
    if native[126] != 1 or native[128:135] != bytes.fromhex("020353f0e27802"):
        raise ValueError("Unexpected native HDMI extension-count override")

    native = sanitize_identity(native)
    cta = native[256:384]
    if cta[:4] != bytes.fromhex("020349f0"):
        raise ValueError("Unexpected native timing extension")
    timings = []
    offset = 4
    while offset < cta[2]:
        header = cta[offset]
        length = header & 0x1F
        payload = cta[offset + 1:offset + 1 + length]
        if offset + 1 + length > cta[2]:
            raise ValueError("Truncated CTA data block")
        if header >> 5 == 7 and payload[:1] == b"\x22":
            if length != 22 or payload[1] != 2:
                raise ValueError("Unexpected CTA Type VII timing layout")
            timing = bytearray(payload[2:])
            clock_khz = int.from_bytes(timing[:3], "little") + 1
            if clock_khz % 10:
                raise ValueError("Clock cannot be represented exactly in Type I")
            # Type VII uses 1 kHz units; Type I uses 10 kHz. Both encode N-1.
            timing[:3] = (clock_khz // 10 - 1).to_bytes(3, "little")
            timings.append(timing)
        offset += length + 1
    clocks = [int.from_bytes(t[:3], "little") * 10 + 10 for t in timings]
    if clocks != [937750, 1667170, 1111250]:
        raise ValueError("Expected native 1080p360, 1440p360 and 1440p240 timings")

    # Retain the native 120 Hz preference, with identical porches to 360 Hz.
    preferred = bytearray(timings[1])
    preferred[:3] = (555720 // 10 - 1).to_bytes(3, "little")
    preferred[3] |= 0x80
    timings.insert(0, preferred)
    # Display parameters: native image size, QHD panel, audio, gamma 2.2,
    # 16:9 aspect, 10-bit panel (also advertised by this monitor over DP).
    parameters = (bytes([0x01, 0x00, 12])
                  + (native[21] * 100).to_bytes(2, "little")
                  + (native[22] * 100).to_bytes(2, "little")
                  + (2560).to_bytes(2, "little")
                  + (1440).to_bytes(2, "little")
                  + bytes([0x80, native[23], 78, 0x99]))
    payload = parameters + bytes([0x03, 0x01, 80]) + b"".join(timings)
    extension = bytearray(128)
    extension[:5] = bytes([0x70, 0x12, len(payload), 0x03, 0x00])
    extension[5:5 + len(payload)] = payload
    inner_checksum = 5 + len(payload)
    extension[inner_checksum] = (-sum(extension[1:inner_checksum])) & 0xFF
    checksum(extension)

    result = bytearray(native)
    # HDMI Forum count override requires the base count to remain one.
    result[134] = 3
    # Linux 7.2 populate_hdmi_info_from_connector tests bpc_supported == 10
    # versus == 12, while drm_parse_dsc_info records the highest supported bpc.
    # Advertising both makes AMDGPU reject 10-bit DSC. Advertise only 10-bit
    # DSC until the driver handles lower depths too; leave TMDS deep color alone.
    # https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_helpers.c
    if native[163:167] != bytes.fromhex("6dd85dc4") or native[174] != 0xC3:
        raise ValueError("Unexpected native HDMI Forum DSC capability block")
    result[174] &= ~0x02  # DRM_EDID_DSC_12BPC; retain DSC_10BPC and DSC_1P2.
    first_cta = result[128:256]
    checksum(first_cta)
    result[128:256] = first_cta
    result.extend(extension)

    if result[174] != 0xC1:
        raise ValueError("Expected 10-bit DSC without 12-bit DSC")
    if any(a != b and i not in {134, 174, 255}
           for i, (a, b) in enumerate(zip(native, result))):
        raise ValueError("Native capabilities or timings unexpectedly changed")
    if any(sum(result[i:i + 128]) % 256 for i in range(0, len(result), 128)):
        raise ValueError("Invalid generated EDID checksum")
    if sum(extension[1:inner_checksum + 1]) % 256:
        raise ValueError("Invalid generated DisplayID checksum")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 generate_edid.py INPUT.bin OUTPUT.bin")
    source, destination = map(Path, sys.argv[1:])
    destination.write_bytes(patch(source.read_bytes()))
