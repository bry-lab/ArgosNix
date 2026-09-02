# The reference live system.
#
# Design decisions worth knowing before you change anything here:
#
#   * Ephemeral by default. The live user's home is tmpfs and there is no
#     persistence partition. An engagement box that quietly accumulates client
#     data across jobs is a breach waiting to happen; if you want persistence,
#     mount it explicitly at /loot.
#
#   * No default password of "kali". The live user has no password and no
#     remote login path; sudo is passwordless *from console only*. This is the
#     same posture as a live CD but without the well-known credential.
#
#   * Profiles are a parameter, not a fixed set. A full-everything ISO is
#     20GB+ and takes an hour to build. Build the one you need:
#       nix build .#iso --override-input profiles '["network" "ad"]'
#     or import this file with your own programs.arsenal.profiles.
{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [
    "${modulesPath}/installer/cd-dvd/installation-cd-minimal.nix"
  ];

  programs.arsenal = {
    enable = true;
    profiles = lib.mkDefault [ "recon" "network" "webapp" "ad" "revuln" ];
    users = [ "arsenal" ];
    capabilities.enable = true;
    hardware = {
      wireless = true;
      sdr = true;
      smartcard = true;
      android = true;
    };
  };

  # -- identity ---------------------------------------------------------
  networking.hostName = "arsenal";
  users.users.arsenal = {
    isNormalUser = true;
    description = "nix-arsenal live user";
    extraGroups = [ "wheel" "networkmanager" "wireshark" "dialout" "plugdev" ];
    initialHashedPassword = "";
  };

  security.sudo.wheelNeedsPassword = false;
  services.getty.autologinUser = lib.mkDefault "arsenal";

  # No sshd on the live image. If you need remote access you can start it
  # deliberately; having one listening by default on an engagement network is
  # an own-goal.
  services.openssh.enable = lib.mkDefault false;

  # -- desktop ----------------------------------------------------------
  # Sway rather than a full DE: fast to build, low RAM, and the tooling here is
  # overwhelmingly terminal-first. Xwayland is on because Burp, Ghidra and
  # Wireshark are all Java or GTK apps that expect X.
  programs.sway = {
    enable = true;
    wrapperFeatures.gtk = true;
    extraPackages = with pkgs; [
      foot
      wofi
      waybar
      swaylock
      wl-clipboard
      grim
      slurp
      firefox
    ];
  };
  hardware.graphics.enable = true;
  security.polkit.enable = true;
  services.dbus.enable = true;

  # -- ephemerality -----------------------------------------------------
  fileSystems."/home/arsenal" = {
    fsType = "tmpfs";
    options = [ "mode=0755" "size=4G" ];
    neededForBoot = true;
  };

  # Somewhere to deliberately persist evidence. Mount a real device here.
  systemd.tmpfiles.rules = [
    "d /loot 0750 arsenal users -"
  ];

  # -- posture ----------------------------------------------------------
  networking.networkmanager.enable = true;
  networking.firewall.enable = lib.mkDefault true;

  # Offensive tooling and DNS-over-HTTPS resolvers interact badly: half your
  # recon goes out over the resolver instead of the interface you think.
  services.resolved.enable = false;

  # MAC randomisation on by default. Turn it off per-interface when you need a
  # stable MAC for a captive portal or a licence check.
  networking.networkmanager.wifi.macAddress = lib.mkDefault "random";

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    substituters = [
      "https://cache.nixos.org"
      "https://arsenal.cachix.org" # replace with your own cache
    ];
    trusted-public-keys = [
      "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
      # "arsenal.cachix.org-1:REPLACE_ME"
    ];
  };

  isoImage = {
    isoName = lib.mkForce "nix-arsenal-${config.system.nixos.label}-${pkgs.stdenv.hostPlatform.system}.iso";
    volumeID = lib.mkForce "ARSENAL";
    squashfsCompression = "zstd -Xcompression-level 6";
    makeEfiBootable = true;
    makeUsbBootable = true;
  };

  system.stateVersion = "25.05";
}
