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
{ config, pkgs, ... }:

let
  username = "hacker";   # <-- your login name
  keepDays = 7;          # garbage-collect generations older than this
in
{
  # --- Boot ---------------------------------------------------------------
  # Default: UEFI, which covers most modern VMs (QEMU/OVMF, UTM, VMware, and
  # VirtualBox with EFI enabled).
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  # Legacy BIOS VM instead? Comment the two lines above and use these, pointing
  # `device` at the VM's disk (often /dev/vda or /dev/sda):
  #   boot.loader.grub.enable = true;
  #   boot.loader.grub.device = "/dev/vda";

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

  # --- Base packages (security tools come from Argos, not from here) ------
  environment.systemPackages = with pkgs; [
    # Basics
    git curl wget vim neovim tree htop tmux file unzip p7zip python3

    # Networking basics
    net-tools        # ifconfig, netstat, route
    dnsutils         # dig, nslookup

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
