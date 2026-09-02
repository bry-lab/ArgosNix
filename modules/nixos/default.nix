# NixOS module.
#
# This is where nix-arsenal stops being a package list and starts being a
# credible distro replacement. A devShell can put nmap on your PATH; it cannot
# give it CAP_NET_RAW, load an mac80211 monitor-mode driver, or write a udev
# rule so your Proxmark is readable without sudo. Kali's real value was never
# the package selection -- it was that all of that was already done.
#
# Everything here is derived from the catalog's `capabilities` field, so adding
# a tool that needs raw sockets is a one-line catalog edit, not a module edit.
{ catalog }:

{ config, lib, pkgs, ... }:

let
  cfg = config.programs.arsenal;

  profiles = import ../../nix/profiles.nix { inherit lib pkgs catalog; };

  selectedPackages = lib.unique
    (lib.concatMap profiles.packagesFor cfg.profiles);

  # Tools in the selected profiles that declared a given capability, resolved to
  # real packages. This is what drives the wrapper set.
  toolsWithCapability = capability:
    let
      wanted = lib.unique (lib.concatMap profiles.toolsFor cfg.profiles);
    in
    lib.filter
      (tool: builtins.elem capability tool.capabilities && tool.attr != null)
      wanted;

  resolve = tool: lib.attrByPath (lib.splitString "." tool.attr) null pkgs;

  # setcap wrappers. Note the deliberate narrowness: cap_net_raw+cap_net_admin
  # and nothing else, owned by root, group-restricted to cfg.group. A wrapper
  # with cap_setuid would be a local privilege escalation on a machine whose
  # entire purpose is running other people's code.
  capWrapper = caps: tool:
    let pkg = resolve tool;
    in lib.optionalAttrs (pkg != null && pkg.meta ? mainProgram) {
      ${pkg.meta.mainProgram} = {
        source = lib.getExe pkg;
        capabilities = caps;
        owner = "root";
        group = cfg.group;
        permissions = "u+rx,g+x,o=";
      };
    };

in
{
  options.programs.arsenal = {
    enable = lib.mkEnableOption "the nix-arsenal security toolset";

    profiles = lib.mkOption {
      type = lib.types.listOf (lib.types.enum profiles.names);
      default = [ ];
      example = [ "network" "ad" "webapp" ];
      description = ''
        Which tool profiles to install system-wide. Profiles overlap; packages
        are deduplicated. Installing "full" is supported but will pull several
        gigabytes and is rarely what you want on a working machine.
      '';
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "arsenal";
      description = ''
        Group permitted to use capability-wrapped tools. Members can craft raw
        packets and capture traffic, which is close enough to root on a shared
        machine that you should treat membership as an admin grant.
      '';
    };

    users = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "alice" ];
      description = "Users to add to the arsenal group.";
    };

    capabilities = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Install setcap wrappers for tools that declared they need raw sockets,
          packet capture or interface control. Disable on a shared or
          multi-tenant host.
        '';
      };
    };

    hardware = {
      wireless = lib.mkEnableOption "monitor-mode capable wireless firmware and drivers";
      sdr = lib.mkEnableOption "SDR device rules and drivers (RTL-SDR, HackRF, bladeRF)";
      smartcard = lib.mkEnableOption "smartcard, RFID and NFC device rules (Proxmark, ACR122U)";
      android = lib.mkEnableOption "adb/fastboot device rules for mobile testing";
    };

    detonation = {
      enable = lib.mkEnableOption ''
        an isolated VM host setup for malware detonation. Enables libvirt with
        no host networking bridge by default -- read modules/nixos/detonation.nix
        before pointing this at live samples
      '';
    };
  };

  config = lib.mkIf cfg.enable (lib.mkMerge [
    {
      environment.systemPackages = selectedPackages;

      users.groups.${cfg.group} = { };
      users.users = lib.genAttrs cfg.users (_: {
        extraGroups = [ cfg.group ];
      });

      # Tool caches, template repos and wordlist updates need somewhere writable
      # that is not the store. Nuclei alone will try to write to $HOME on first
      # run and fail confusingly if this is not set.
      environment.sessionVariables = {
        SECLISTS = "${pkgs.seclists}/share/seclists";
        ARSENAL_PROFILES = lib.concatStringsSep "," cfg.profiles;
      };
    }

    (lib.mkIf cfg.capabilities.enable {
      security.wrappers = lib.mkMerge (
        map (capWrapper "cap_net_raw+ep") (toolsWithCapability "raw-socket")
        ++ map (capWrapper "cap_net_raw,cap_net_admin+ep") (toolsWithCapability "net-admin")
        ++ map (capWrapper "cap_net_raw,cap_net_admin+ep") (toolsWithCapability "packet-capture")
      );

      # dumpcap already has a first-class NixOS option that gets the group
      # membership and permissions right. Use it rather than hand-rolling.
      programs.wireshark = {
        enable = lib.mkDefault true;
        package = lib.mkDefault pkgs.wireshark;
      };
      users.groups.wireshark = { };
    })

    (lib.mkIf cfg.hardware.wireless {
      hardware.enableRedistributableFirmware = true;
      # Realtek and Atheros adapters that people actually buy for monitor mode
      # need out-of-tree drivers. Keep this list short and current; each entry
      # is a kernel rebuild risk on every kernel bump.
      boot.extraModulePackages = with config.boot.kernelPackages; [
        rtl8812au
      ];
      networking.networkmanager.unmanaged = [
        # Leave monitor-mode interfaces alone; NetworkManager will otherwise
        # fight airmon-ng for control and you will lose an hour to it.
        "interface-name:wlan*mon"
        "interface-name:mon*"
      ];
    })

    (lib.mkIf cfg.hardware.sdr {
      environment.systemPackages = with pkgs; [ rtl-sdr hackrf soapysdr-with-plugins ];
      services.udev.packages = with pkgs; [ rtl-sdr hackrf ];
      # The kernel DVB driver grabs RTL dongles before SDR software can.
      boot.blacklistedKernelModules = [ "dvb_usb_rtl28xxu" ];
    })

    (lib.mkIf cfg.hardware.smartcard {
      services.pcscd.enable = true;
      services.udev.packages = with pkgs; [ proxmark3-rrg libnfc ];
      environment.systemPackages = with pkgs; [ pcsctools libnfc ];
    })

    (lib.mkIf cfg.hardware.android {
      programs.adb.enable = true;
      services.udev.packages = [ pkgs.android-udev-rules ];
    })

    (lib.mkIf cfg.detonation.enable {
      virtualisation.libvirtd = {
        enable = true;
        qemu.swtpm.enable = true;
      };
      # No default bridge. Detonation VMs get an isolated network explicitly or
      # they get nothing; the failure mode of getting this wrong is your own
      # network becoming part of the sample's lateral movement.
      virtualisation.libvirtd.onBoot = "ignore";
      networking.firewall.checkReversePath = false;
    })
  ]);
}
