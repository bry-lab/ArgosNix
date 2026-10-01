# Drop-in NixOS VM

A complete NixOS system you can copy onto a freshly installed VM, rebuild once,
and then use Argos on. For composing Argos into an *existing* system instead, see
[../configuration.nix](../configuration.nix).

## Use it

On a fresh NixOS VM (after the normal graphical/minimal install), you already
have `/etc/nixos/configuration.nix` and `/etc/nixos/hardware-configuration.nix`.

1. Copy the two files here over the top, **keeping** your generated
   `hardware-configuration.nix`:

   ```sh
   cd /etc/nixos
   sudo curl -L -O https://raw.githubusercontent.com/bry-lab/ArgosNix/main/examples/nixos-vm/flake.nix
   sudo curl -L -O https://raw.githubusercontent.com/bry-lab/ArgosNix/main/examples/nixos-vm/configuration.nix
   ```

2. Edit `configuration.nix`: set `username`, and set `system.stateVersion` to
   the output of `nixos-version`. The boot loader needs no edit — UEFI vs
   legacy BIOS is detected from your `hardware-configuration.nix` and the right
   loader (systemd-boot or GRUB) is selected automatically.

3. Build it:

   ```sh
   sudo nixos-rebuild switch --flake /etc/nixos#argos-vm
   ```

   On an ARM VM (e.g. UTM on an M-series Mac), use the aarch64 system instead:

   ```sh
   sudo nixos-rebuild switch --flake /etc/nixos#argos-vm-aarch64
   ```

4. Reboot, log in, change your password (`passwd`), then install tools per use
   case:

   ```sh
   nix profile install github:bry-lab/ArgosNix#revuln   # reverse engineering
   nix profile install github:bry-lab/ArgosNix#osint    # OSINT
   nix profile list
   nix profile remove osint                             # offload one, keep the rest
   ```

## What you get

A working, networked base system with a Cinnamon desktop, LibreWolf and VS Code,
flakes, automatic garbage collection, `nix-ld` (so prebuilt CTF binaries run),
VM guest integration, and a small set of everyday CLI tools. (The desktop block
in `configuration.nix` is easy to swap for Xfce/Plasma or comment out for a
headless system.) **No security tools are installed by default** — you add them
with `nix profile install` above, or uncomment the `programs.argos` block in
`configuration.nix` to bake a set in and get the capability layer (raw sockets,
monitor mode, udev rules) that a user profile cannot grant.

## Troubleshooting

### `Failed to install bootloader` on a legacy-BIOS VM

The boot loader is auto-selected: a UEFI machine (vfat ESP at `/boot` or
`/boot/efi` in your `hardware-configuration.nix`) gets systemd-boot, anything
else gets GRUB. The one assumption left is the **disk GRUB installs to**, which
defaults to `/dev/vda` (the virtio disk used by QEMU/KVM/libvirt/UTM). If your
BIOS VM uses SATA/IDE instead (VirtualBox, VMware, older QEMU), override it in
`configuration.nix`:

```sh
lsblk        # find the whole disk: sda? vda?
```

```nix
boot.loader.grub.device = "/dev/sda";
```

then rebuild. (If you see `efiSysMountPoint ... is not a mounted partition`, you
are on an older copy of this config that hard-coded systemd-boot — pull the
current one.)

### `systemd-run: unrecognized option '--output=cat'`

Seen on VMs whose base image ships an **old systemd** that the newer
`nixos-rebuild` activation wrapper does not support. The build still succeeds; only
the activation wrapper fails. Build without activating, then activate the result
directly and reboot:

```sh
cd /etc/nixos
sudo nixos-rebuild build --flake /etc/nixos#argos-vm
sudo NIXOS_INSTALL_BOOTLOADER=1 ./result/bin/switch-to-configuration boot
sudo reboot
```

After rebooting into the new system (which has a current systemd), the normal
`sudo nixos-rebuild switch --flake /etc/nixos#argos-vm` works from then on.
