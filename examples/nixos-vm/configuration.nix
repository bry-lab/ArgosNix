# A complete, drop-in NixOS system for a fresh VM you want to use with Argos.
#
# Unlike ../configuration.nix (which is a partial module you compose into an
# existing system), this is a whole system config. You replace the installer's
# /etc/nixos/configuration.nix with this one and keep the
# hardware-configuration.nix the installer generated.
#
# Steps on a freshly installed NixOS VM:
#   1. Copy this file and the flake.nix next to it into /etc/nixos/, overwriting
#      the stock configuration.nix. Do NOT touch hardware-configuration.nix.
#   2. Set `username` below. If your VM boots legacy BIOS rather than UEFI, swap
#      the boot loader (see the Boot section).
#   3. sudo nixos-rebuild switch --flake /etc/nixos#argos-vm
#   4. Install whatever you need, per use case, and remove it when done:
#        nix profile install github:bry-lab/ArgosNix#revuln
#        nix profile install github:bry-lab/ArgosNix#osint
#        nix profile remove osint
#
# This boots to a working base system (networking, a user, flakes, automatic GC,
# nix-ld, VM guest integration) with the Argos module available. It installs NO
# security tools by default -- you add those with `nix profile install`, or flip
# on the declarative block at the bottom to bake a set in (and get capabilities).
{ config, pkgs, lib, ... }:

let
  username = "hacker";   # <-- your login name
  keepDays = 7;          # garbage-collect generations older than this

  # Detect firmware from the hardware config the installer generated: a UEFI
  # system mounts an EFI system partition (vfat) at /boot or /boot/efi, a BIOS
  # system does not. This is what lets one configuration.nix boot on both.
  bootIsUEFI =
    (config.fileSystems ? "/boot" && config.fileSystems."/boot".fsType == "vfat")
    || (config.fileSystems ? "/boot/efi" && config.fileSystems."/boot/efi".fsType == "vfat");
in
{
  # --- Boot (auto-selected: UEFI -> systemd-boot, BIOS -> GRUB) -----------
  # Chosen from bootIsUEFI above, so this same file works on a UEFI VM and a
  # legacy-BIOS VM with no edits. All of these are mkDefault, so you can still
  # override any of them for an unusual setup.
  boot.loader.systemd-boot.enable = lib.mkDefault bootIsUEFI;
  boot.loader.efi.canTouchEfiVariables = lib.mkDefault bootIsUEFI;
  boot.loader.efi.efiSysMountPoint =
    lib.mkDefault (if config.fileSystems ? "/boot/efi" then "/boot/efi" else "/boot");

  boot.loader.grub.enable = lib.mkDefault (!bootIsUEFI);
  # BIOS only: the disk GRUB installs its boot record to. Defaults to the virtio
  # disk most VMs use (QEMU/KVM/libvirt/UTM). If your BIOS VM uses SATA/IDE
  # (VirtualBox, VMware, older QEMU) this is /dev/sda -- confirm with `lsblk`.
  boot.loader.grub.device = lib.mkDefault "/dev/vda";

  # --- Nix ----------------------------------------------------------------
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    auto-optimise-store = true; # deduplicate identical files in the store
  };
  nix.gc = {
    automatic = true;
    dates = "daily";
    options = "--delete-older-than ${toString keepDays}d";
  };

  # Lets precompiled binaries (CTF challenges, downloaded tools) run on NixOS.
  programs.nix-ld.enable = true;

  # --- Identity, network, access -----------------------------------------
  networking.hostName = "argos-vm";
  networking.networkmanager.enable = true;

  time.timeZone = "UTC";                 # e.g. "America/New_York"
  i18n.defaultLocale = "en_US.UTF-8";

  users.users.${username} = {
    isNormalUser = true;
    description = username;
    extraGroups = [ "wheel" "networkmanager" ];
    initialPassword = "changeme";        # change after first login with: passwd
  };
  security.sudo.wheelNeedsPassword = true;

  # --- VM guest niceties (shared clipboard, better integration) -----------
  services.spice-vdagentd.enable = true;
  services.qemuGuest.enable = true;

  # --- Desktop -------------------------------------------------------------
  # MATE: light enough for a VM, nicer-looking than stock Xfce. Swap the
  # desktopManager line for xfce.enable or plasma6 (see NixOS options) if you
  # prefer; comment the block out entirely for a headless system.
  services.xserver.enable = true;
  services.xserver.desktopManager.mate.enable = true;

  # Unfree packages, allowed by name only -- never blanket. vscode is why this
  # exists; the others are the unfree tools Argos profiles can pull in when you
  # enable programs.argos with the dfir/malware profiles.
  nixpkgs.config.allowUnfreePredicate = pkg:
    builtins.elem (lib.getName pkg) [
      "vscode"
      "volatility3" "obsidian" "wpscan" "waybackurls"
    ];

  # --- Base packages (security tools come from Argos, not from here) ------
  environment.systemPackages = with pkgs; [
    # Basics
    git curl wget vim neovim tree htop tmux file unzip p7zip python3

    # Networking basics
    net-tools        # ifconfig, netstat, route
    dnsutils         # dig, nslookup

    # Desktop apps
    librewolf        # hardened Firefox fork
    vscode           # unfree -- allowed by the predicate above

    # Fun
    hollywood
    cmatrix
    cbonsai
  ];

  # --- Optional: bake an Argos set into the system ------------------------
  # Leave this off and install per use case with `nix profile install
  # ...#<profile>`. Turn it on to install a set declaratively AND get the
  # capabilities a user profile cannot grant: raw sockets, monitor mode, udev.
  # programs.argos = {
  #   enable = true;
  #   profiles = [ "revuln" "osint" ];
  #   users = [ username ];
  #   capabilities.enable = true;
  #   # hardware.wireless = true;   # monitor-mode Wi-Fi drivers
  #   # hardware.sdr = true;        # RTL-SDR / HackRF rules
  # };

  # Set this to the NixOS release you installed from, and do NOT change it on
  # later upgrades. Check yours with: nixos-version
  system.stateVersion = "25.05";
}
