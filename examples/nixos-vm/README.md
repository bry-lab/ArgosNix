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
