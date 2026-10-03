{ pkgs, ... }:
let
  g60sdEdid = pkgs.runCommand "g60sd-hdmi-edid" { } ''
    mkdir -p "$out/lib/firmware/edid"
    cp ${./g60sd-hdmi.bin} "$out/lib/firmware/edid/g60sd-hdmi.bin"
  '';
in
{
  # Linux 7.2 FRL bit (0x400) plus the tested system's existing bit (0x2).
  # Review your existing feature mask before using this value.
  boot.kernelParams = [ "amdgpu.dcfeaturemask=0x402" ];

  hardware.display.edid.packages = [ g60sdEdid ];
  hardware.display.outputs."HDMI-A-1".edid = "g60sd-hdmi.bin";
  # Enable only if the G60SD is connected to the other GPU HDMI port.
  # hardware.display.outputs."HDMI-A-2".edid = "g60sd-hdmi.bin";
  boot.initrd.extraFirmwarePaths = [ "edid/g60sd-hdmi.bin" ];
}
