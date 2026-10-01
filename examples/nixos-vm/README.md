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

2. Edit `configuration.nix`: set `username`, set `system.stateVersion` to the
   output of `nixos-version`, and — only if your VM is legacy BIOS rather than
   UEFI — switch the boot loader (see the comment in the Boot section).

3. Build it:

   ```sh
   sudo nixos-rebuild switch --flake /etc/nixos#argos-vm
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

A working, networked base system with flakes, automatic garbage collection,
`nix-ld` (so prebuilt CTF binaries run), VM guest integration, and a small set of
everyday CLI tools. **No security tools are installed by default** — you add them
with `nix profile install` above, or uncomment the `programs.argos` block in
`configuration.nix` to bake a set in and get the capability layer (raw sockets,
monitor mode, udev rules) that a user profile cannot grant.

## Troubleshooting

### `efiSysMountPoint = '/boot' is not a mounted partition` / `Failed to install bootloader`

The config defaults to `systemd-boot`, which is UEFI-only. This error means your
VM boots **legacy BIOS**, so you need GRUB instead. Confirm, then switch loaders:

```sh
[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS   # BIOS = use grub
lsblk                                                 # find the disk (vda/sda)
```

In `configuration.nix`, comment the two `systemd-boot`/`efi` lines and enable:

```nix
boot.loader.grub.enable = true;
boot.loader.grub.device = "/dev/vda";   # the whole disk from lsblk
```

then rebuild.

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
