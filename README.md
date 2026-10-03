# Enable HDMI FRL and DSC on the Samsung Odyssey G60SD

Use this EDID override to enable 2560×1440 at 360 Hz with 10-bit color on a Samsung Odyssey OLED G60SD.

The fix works on the tested AMD Navi 48 GPU with CachyOS Linux 7.2.8 and KDE Plasma on Wayland. The test used the monitor's HDMI 2 input. Other GPUs, kernels, and monitor firmware versions remain untested.

## Prepare the connection

Use this override only with a G60SD. Your GPU and driver must support HDMI FRL and DSC.

The override disables 12-bit DSC to avoid a driver bug. It retains 10-bit DSC and uncompressed HDMI deep-color support.

Connect the monitor to the GPU with an Ultra High Speed HDMI cable. Disable HDR and VRR for the initial test. This setup has not been tested with HDR, VRR, or suspend and resume.

Keep a DisplayPort connection or a previous boot entry available for recovery. Download the files:

```sh
git clone https://github.com/controlled-opposition/linux-hdmi-2.1-G60SD.git
cd linux-hdmi-2.1-G60SD
```

Find the connected GPU connector:

```sh
grep -H . /sys/class/drm/card*-HDMI-A-*/status
```

Use that connector name in the configuration below. `HDMI-A-1` identifies a GPU connector, not the monitor's HDMI 1 input. Do not apply the override to a connector used by another monitor.

On the tested kernel, `0x400` enables AMDGPU FRL. Preserve your existing feature bits. This command prints the combined kernel parameter:

```sh
mask=$(cat /sys/module/amdgpu/parameters/dcfeaturemask)
printf 'amdgpu.dcfeaturemask=0x%x\n' "$((mask | 0x400))"
```

The tested system used `amdgpu.dcfeaturemask=0x402`. Use the value printed for your system.

## Install on NixOS

1. Copy [`nixos.nix`](./nixos.nix) and [`g60sd-hdmi.bin`](./g60sd-hdmi.bin) into your configuration directory. Keep the files next to each other.
2. Import `nixos.nix` from your host configuration.
3. Set the connector name and feature mask in `nixos.nix`. The module includes a commented option for `HDMI-A-2`.
4. Build and install a boot generation with your usual NixOS rebuild command.
5. Reboot.

## Install on another Linux distribution

1. Install the EDID file:

	```sh
	sudo install -Dm644 g60sd-hdmi.bin /lib/firmware/edid/g60sd-hdmi.bin
	```

2. Add these kernel parameters to your bootloader configuration. Replace the feature mask and connector name with the values from the preparation steps.

	```text
	amdgpu.dcfeaturemask=0x402 drm.edid_firmware=HDMI-A-1:edid/g60sd-hdmi.bin
	```

3. Include `/lib/firmware/edid/g60sd-hdmi.bin` in the initramfs. On a mkinitcpio-based system, append that path to the existing `FILES` array in `/etc/mkinitcpio.conf`.
4. Regenerate the initramfs with your distribution's tool. For mkinitcpio, run `sudo mkinitcpio -P`.
5. Update the bootloader configuration if your distribution requires that step.
6. Reboot.

## Select the display mode

In KDE Display settings, select 2560×1440 at 360 Hz. Leave **Color resolution** on **Automatic**.

Automatic selects 10-bit color on the tested setup. You do not need to select 10-bit explicitly. The override keeps 120 Hz as the preferred mode, so select 360 Hz after installation.

## Verify the active mode and color depth

Check the active mode:

```sh
kscreen-doctor -o
```

Look for an active 2560×1440 mode at 360 Hz and **automatic (10)** under **Color resolution**.

Read the driver's stream color depth:

```sh
sudo cat /sys/kernel/debug/dri/1/crtc-0/amdgpu_current_bpc
```

The expected output is `Current: 10`. The GPU and CRTC numbers can differ on your system. Read the active CRTC on the GPU connected to the monitor. An inactive CRTC returns `No such device`.

If Automatic selects 8-bit color, select 10-bit in KDE and repeat the check. Use `amdgpu_current_bpc` to verify color depth. The HDMI hardware dump can report `Depth: 8` during DSC even when the stream uses 10-bit color.

## Remove the override

After a monitor firmware or kernel update, check whether you still need the override. Linux continues to use the override until you remove it.

1. Remove the `nixos.nix` import or the `drm.edid_firmware` kernel parameter, according to your installation method.
2. Restore your previous AMDGPU feature mask.
3. Rebuild NixOS or regenerate the initramfs and bootloader configuration.
4. Reboot.

If the display fails, boot the previous working entry or use DisplayPort to remove the override.

## Acknowledgments

[legin449/linux-hdmi-2.1-G80SD](https://github.com/legin449/linux-hdmi-2.1-G80SD) provided the approach for exposing high-refresh timings. This repository uses the G60SD's native timings and capabilities, not the G80SD EDID.
