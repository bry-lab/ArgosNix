# Example NixOS configuration for an Argos workstation or VM.
#
# This is the "base system" layer: sensible Nix settings, automatic garbage
# collection, a few everyday CLI tools, and VM guest niceties. The security
# tooling itself comes from Argos via `programs.argos` below, so you never
# hand-list security packages here.
#
# How to use it (flake-based system, recommended) -- in your flake.nix:
#
#     inputs.argos.url = "github:bry-lab/ArgosNix";
#     outputs = { nixpkgs, argos, ... }: {
#       nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
#         system = "x86_64-linux";
#         modules = [
#           argos.nixosModules.argos   # provides the programs.argos options
#           ./configuration.nix        # this file
#           ./hardware-configuration.nix
#         ];
#       };
#     };
#
#   then:  sudo nixos-rebuild switch --flake .#myhost
#
# If you would rather keep a plain base system and pull Argos tools ad hoc with
# `nix profile install github:bry-lab/ArgosNix#<profile>`, simply delete the
# `programs.argos` block below -- nothing else here depends on it.
{ config, pkgs, ... }:

let
  # Delete old generations and unused packages after this many days.
  keepDays = 7;
in
{
  # --- Nix settings -------------------------------------------------------
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    auto-optimise-store = true; # deduplicate identical files in the store
  };

  # Automatic garbage collection.
  nix.gc = {
    automatic = true;
    dates = "daily";
    options = "--delete-older-than ${toString keepDays}d";
  };

  # Lets precompiled CTF challenge binaries run on NixOS.
  programs.nix-ld.enable = true;

  # --- Argos: the security tooling ---------------------------------------
  # Everything security-related loads from here instead of being hand-listed.
  # Requires argos.nixosModules.argos to be imported (see the header). This is
  # also where you get capabilities a plain `nix profile install` cannot grant:
  # raw sockets, monitor-mode drivers, udev rules.
  programs.argos = {
    enable = true;
    profiles = [ "osint" "network" "webapp" "ad" "revuln" ];
    users = [ "you" ];            # add your login name to the argos group
    capabilities.enable = true;   # setcap wrappers for raw sockets, capture, ...
    # hardware.wireless = true;   # monitor-mode capable Wi-Fi drivers
    # hardware.sdr = true;        # RTL-SDR / HackRF device rules
  };

  # --- VM guest niceties (shared clipboard, better integration) -----------
  services.spice-vdagentd.enable = true;
  services.qemuGuest.enable = true;

  # --- Base packages (everything else loads from Argos) -------------------
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

  # Set this to the NixOS release you first installed from, and do not change it
  # on later upgrades.
  # system.stateVersion = "25.05";
}
