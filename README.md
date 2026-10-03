# Samsung Odyssey G60SD: Linux HDMI FRL + DSC workaround

Enables **2560×1440 at 360 Hz with 10-bit color over HDMI FRL + DSC** on the Samsung Odyssey OLED G60SD.

Tested with an AMD Navi 48 / RX 9070-family GPU, CachyOS Linux **7.2.8**, KDE Plasma on Wayland, and the monitor's **HDMI 2 input**. Other hardware/kernel combinations are not verified. This requires a driver and GPU with FRL + DSC support; an EDID override cannot add that support.

## Install

```sh
git clone https://github.com/controlled-opposition/linux-hdmi-2.1-G60SD.git
cd linux-hdmi-2.1-G60SD
```

Use a direct GPU HDMI connection and an Ultra High Speed HDMI cable. Start with **HDR and VRR disabled**; they and suspend/resume have not been tested. Keep a working DisplayPort connection or previous boot entry available for recovery. Use this EDID only with a G60SD.

### NixOS

1. Copy [`nixos.nix`](./nixos.nix) and [`g60sd-hdmi.bin`](./g60sd-hdmi.bin) into your configuration directory, keeping them next to each other.
2. Import `nixos.nix` in your host configuration. Review the GPU connector name and AMDGPU feature mask in that file.
3. Build/install a boot generation and reboot.

The module targets **`HDMI-A-1`**, with a commented `HDMI-A-2` alternative. These are GPU connector names, not the monitor's physical input numbers. Apply the override only to the connector used by the G60SD.

### Other Linux distributions

1. Identify the connected GPU connector:

   ```sh
   grep -H . /sys/class/drm/card*-HDMI-A-*/status
   ```

2. Install the EDID:

   ```sh
   sudo install -Dm644 g60sd-hdmi.bin /lib/firmware/edid/g60sd-hdmi.bin
   ```

3. Add these kernel parameters to your bootloader configuration, replacing `HDMI-A-1` if needed:

   ```text
   amdgpu.dcfeaturemask=0x402 drm.edid_firmware=HDMI-A-1:edid/g60sd-hdmi.bin
   ```

   On the tested kernel, FRL is the `0x400` feature bit. `0x402` preserves the tested system's existing `0x2` bit. Check `/sys/module/amdgpu/parameters/dcfeaturemask` and preserve your existing feature bits rather than blindly replacing the mask.

4. Include `/lib/firmware/edid/g60sd-hdmi.bin` in the initramfs, regenerate it, and update your bootloader as required by your distribution. On **mkinitcpio-based systems**, append that path to the existing `FILES` array in `/etc/mkinitcpio.conf`, then run:

   ```sh
   sudo mkinitcpio -P
   ```

5. Reboot.

### KDE display settings

Select **2560×1440 at 360 Hz** and leave **Color resolution on Automatic**. Automatic selected 10-bit on the tested setup after applying the fix; explicitly selecting 10-bit is not required. The EDID keeps 120 Hz preferred, so select 360 Hz manually after installation.

## Verify

```sh
kscreen-doctor -o
sudo cat /sys/kernel/debug/dri/1/crtc-0/amdgpu_current_bpc
```

KDE should show **1440p/360 Hz active** and **automatic (10)**. The driver should report **`Current: 10`**. Debugfs GPU/CRTC numbers may differ; use the active CRTC on the GPU driving the monitor. Inactive CRTCs can return `No such device`.

If Automatic does not select 10-bit, try explicitly selecting 10-bit and repeat the driver check. Do not rely on the HDMI hardware dump's `Depth: 8` field during DSC: the driver clears that register even for a 10-bit stream.

## Limitations and rollback

The override exposes native high-refresh timings and works around an AMDGPU DSC color-depth bug by hiding **12-bit DSC support**. It retains 10-bit DSC and uncompressed HDMI deep-color capabilities. Monitor serial numbers are removed from the supplied EDIDs.

Recheck the workaround after monitor firmware or kernel updates: it continues to replace the native EDID until removed.

To undo it, remove the EDID kernel parameter or NixOS module import, restore your previous AMDGPU feature mask, regenerate the initramfs or rebuild NixOS, and reboot. If the display fails, use the previous working boot entry.

## Acknowledgments

Inspired by [legin449/linux-hdmi-2.1-G80SD](https://github.com/legin449/linux-hdmi-2.1-G80SD). This repository uses G60SD-native timings and capabilities, not the G80SD EDID.
