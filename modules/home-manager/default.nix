# home-manager module.
#
# For people who want the tools on a machine they do not control the OS of --
# Ubuntu at work, a shared box, macOS. You get every binary and none of the
# capabilities: no raw sockets, no monitor mode, no udev rules. That is a real
# limitation, not a bug we will fix, and the module says so at activation time
# rather than letting you discover it mid-engagement.
{ catalog }:

{ config, lib, pkgs, ... }:

let
  cfg = config.programs.arsenal;
  profiles = import ../../nix/profiles.nix { inherit lib pkgs catalog; };

  selected = lib.unique (lib.concatMap profiles.packagesFor cfg.profiles);
  neededCaps = lib.unique (lib.concatMap profiles.capabilitiesFor cfg.profiles);

in
{
  options.programs.arsenal = {
    enable = lib.mkEnableOption "the nix-arsenal security toolset";

    profiles = lib.mkOption {
      type = lib.types.listOf (lib.types.enum profiles.names);
      default = [ ];
      example = [ "osint" "webapp" ];
      description = "Tool profiles to install into this user's environment.";
    };

    quiet = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Suppress the capability warning at activation.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = selected;

    home.sessionVariables = {
      SECLISTS = "${pkgs.seclists}/share/seclists";
    };

    home.activation.arsenalCapabilityWarning =
      lib.mkIf (!cfg.quiet && neededCaps != [ ])
        (lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          $VERBOSE_ECHO "nix-arsenal: ${toString (builtins.length selected)} tools installed."
          $VERBOSE_ECHO "nix-arsenal: these profiles include tools needing ${
            lib.concatStringsSep ", " neededCaps
          }."
          $VERBOSE_ECHO "nix-arsenal: home-manager cannot grant those. Use sudo, or the NixOS module."
        '');
  };
}
