# Samsung Odyssey G60SD: Linux HDMI FRL + DSC workaround

A tested EDID workaround for **2560×1440 at 360 Hz with 10 bits per color over HDMI FRL + DSC** on a Samsung Odyssey OLED G60SD.

Tested with an AMD Navi 48 / RX 9070-family GPU, CachyOS Linux **7.2.8**, KDE Plasma on Wayland, and the monitor's **HDMI 2 input**. The picture was normal during testing. Other GPUs, firmware versions, kernels, and the monitor's HDMI 1 input have not been verified. HDR, HDMI VRR, and suspend/resume have not been tested.

## Files

- `g60sd-hdmi.bin`: ready-to-use 512-byte override.
- `g60sd-hdmi-native-sanitized.bin`: 384-byte HDMI EDID captured from the tested monitor, with both serial-number fields removed.
- `generate_edid.py`: reproducible generator; also removes serial numbers from its input.
- `test_edid.py`: checksum, capability-preservation, and privacy checks. These do not replace a hardware test.
- `nixos.nix`: example NixOS module.

No monitor serial numbers, system logs, host configuration, or credentials are included. The override is based on one monitor's EDID; do not use it for a different monitor model.

## Why this works

There are three separate issues:

1. **FRL is opt-in on the tested kernel.** Linux 7.2 defines the AMDGPU FRL feature bit as `0x400`. The tested system used `amdgpu.dcfeaturemask=0x402`, preserving its existing `0x2` feature bit. Check your existing mask before replacing it; feature masks vary by kernel.
2. **High-refresh timings are not exposed.** The G60SD advertises 1440p/360 Hz and 240 Hz as DisplayID Type VII timings inside a CTA extension. The tested kernel did not expose them as available modes. The override duplicates the exact native timings in a standalone DisplayID 1.2 Type I extension. It keeps 1440p/120 Hz preferred; it does not force 360 Hz at boot.
3. **10-bit DSC is incorrectly rejected when 12-bit DSC is also advertised.** DRM's parser records the highest advertised DSC color depth. AMDGPU's Linux 7.2 conversion checks `bpc_supported == 10` versus `== 12`, enabling only one flag. On this monitor, that disables 10-bit DSC and causes 360 Hz to fall back to 8-bit. The override clears only the **12-bit DSC capability bit**, retaining 10-bit DSC. Uncompressed HDMI deep-color capabilities are unchanged.

Other than identity sanitization, the new extension, its extension-count update, and clearing 12-bit DSC, the captured HDMI capabilities and timings are preserved. The native EDID has manufacture-date conformity errors; the workaround does not repair unrelated metadata.

Sources:

- [Linux 7.2 FRL feature bit](https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/amd/include/amd_shared.h)
- [DRM EDID timing and DSC parsing](https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/drm_edid.c)
- [AMDGPU DSC capability conversion](https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_helpers.c)
- [AMDGPU mode-validation fallback](https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm.c)

## Installation

Keep a working DisplayPort connection or a previous boot entry available for recovery. Start with **HDR and VRR disabled**. Use a direct GPU HDMI connection and a suitable Ultra High Speed HDMI cable.

### NixOS

Copy `nixos.nix` and `g60sd-hdmi.bin` into your configuration directory, keeping them next to each other. Import `nixos.nix` from the relevant host's configuration. Review the feature mask and connector name in that file, then build/install a boot generation and reboot.

The example targets **the GPU connector `HDMI-A-1`**, not the monitor's physical input number. It includes a commented `HDMI-A-2` alternative. Do not apply the override to a port used by a different monitor.

### Other Linux distributions

1. Identify the connected GPU connector:

   ```sh
   grep -H . /sys/class/drm/card*-HDMI-A-*/status
   ```

2. Install the override:

   ```sh
   sudo install -Dm644 g60sd-hdmi.bin /lib/firmware/edid/g60sd-hdmi.bin
   ```

3. Add these kernel parameters, adapting the connector and preserving existing AMDGPU feature bits:

   ```text
   amdgpu.dcfeaturemask=0x402 drm.edid_firmware=HDMI-A-1:edid/g60sd-hdmi.bin
   ```

4. Include `/lib/firmware/edid/g60sd-hdmi.bin` in the initramfs, regenerate it using your distribution's tooling, and update bootloader configuration as required. For example, on a **mkinitcpio-based system**, append this path to the existing `FILES` array in `/etc/mkinitcpio.conf` without replacing other entries, then run `sudo mkinitcpio -P`.
5. Reboot and select **2560×1440 / 360 Hz / explicit 10-bit** in KDE Display settings.

An EDID override cannot add FRL/DSC implementation to an unsupported driver or GPU. These instructions are not a claim that every Linux kernel supports this combination.

## Verification

```sh
cat /sys/module/amdgpu/parameters/dcfeaturemask
kscreen-doctor -o
```

The tested mask returned `1026` (`0x402`). KDE should show 1440p/360 Hz as active and 10 bits per color selected. A listed mode alone is not proof of active FRL/DSC.

Inspect the driver's stream depth and hardware state. Debugfs GPU and CRTC numbers may differ; use the GPU driving the monitor and its active CRTC:

```sh
sudo cat /sys/kernel/debug/dri/1/crtc-0/amdgpu_current_bpc
sudo cat /sys/kernel/debug/dri/1/amdgpu_dm_dtn_log
```

Confirmed in the hardware test:

- `amdgpu_current_bpc`: **`Current: 10`**.
- DSC: two enabled engines, 320-pixel slices, `192` in the legacy `Bytes_pp` column (12 compressed bits per pixel; the value is bits-per-pixel × 16).
- HDMI FRL HPO stream/link encoders enabled on four lanes, with 4:4:4 format reported.
- No timing-generator underflow in the inspected snapshot.

**Do not use the HPO `Depth: 8` field to infer the stream depth during DSC.** The [driver clears that deep-color register when DSC is active](https://github.com/torvalds/linux/blob/v7.2/drivers/gpu/drm/amd/display/dc/hpo/dcn401/dcn401_hpo_frl_stream_encoder.c). Use `amdgpu_current_bpc` instead. Inactive CRTCs can return `No such device`; that is expected.

## Regenerate and test

```sh
python3 generate_edid.py g60sd-hdmi-native-sanitized.bin g60sd-hdmi.bin
python3 -m unittest -v test_edid.py
edid-decode g60sd-hdmi.bin
```

The generator intentionally checks the captured EDID layout and rejects unexpected input. It is not a universal EDID editor. If investigating another firmware revision, capture its native EDID with the override disabled and review any differences before adapting the generator. Captured EDIDs can contain serial numbers: do not publish raw captures or logs without checking them.

## Rollback and limitations

Remove the EDID kernel parameter/module configuration, regenerate the initramfs or rebuild NixOS, and reboot. Remove the FRL feature override too if returning to the previous driver defaults. If necessary, boot the previous working generation.

This override continues to replace the monitor's native EDID after firmware updates. Recheck it after monitor or kernel updates. Once the kernel handles the native timings and DSC depth conversion correctly, test removing the workaround. While enabled, **12-bit DSC is intentionally unavailable**; 10-bit DSC remains advertised.

## Acknowledgment

Inspired by [legin449/linux-hdmi-2.1-G80SD](https://github.com/legin449/linux-hdmi-2.1-G80SD). This repository uses G60SD-native timings and capabilities, not the G80SD EDID.
