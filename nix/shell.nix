# Build a devShell for a profile.
#
# The banner is not decoration. Two things reliably confuse people coming from
# Kali: tools that are in the catalog but not yet packaged, and tools that are
# installed but cannot do their job because a devShell cannot grant CAP_NET_RAW.
# Both get said out loud, every time, rather than buried in a doc nobody reads.
{ lib, pkgs, catalog, profiles }:

let
  capabilityHelp = {
    raw-socket = "raw packet crafting (nmap -sS, hping, naabu)";
    net-admin = "interface manipulation (monitor mode, ARP/DNS spoofing)";
    packet-capture = "live capture (wireshark, tcpdump, zeek)";
    usb = "direct USB device access (SDR, proxmark, flipper)";
    kvm = "hardware virtualisation (detonation VMs)";
    root = "full root";
  };

  mkBanner = name:
    let
      profile = profiles.profiles.${name};
      stats = profiles.statsFor name;
      caps = profiles.capabilitiesFor name;
      missing = profiles.missingFor name;

      capLines = lib.concatMapStringsSep "\n" (c:
        "  ! ${c}: ${capabilityHelp.${c} or "elevated privileges"}") caps;

      missingNote =
        if missing == [ ] then ""
        else ''
          echo "  ${toString stats.missing} catalogued tool(s) are not packaged yet."
          echo "  Run 'arsenal profile ${name} --missing' to see them, or help package one."
        '';

      capNote =
        if caps == [ ] then ""
        else ''
          echo ""
          echo "  Some tools here need privileges a devShell cannot grant:"
          cat <<'CAPS'
          ${capLines}
          CAPS
          echo "  Use the NixOS module (security.wrappers) or prefix with sudo."
        '';
    in
    ''
      echo ""
      echo "  nix-arsenal :: ${name}"
      echo "  ${profile.description}"
      echo "  ${toString stats.available} tools available."
      ${missingNote}
      ${capNote}
      echo ""
    '';

in
{
  mkProfileShell = name:
    pkgs.mkShellNoCC {
      name = "arsenal-${name}";
      packages = profiles.packagesFor name;

      shellHook = ''
        # Wordlists and template corpora live in the store; tools that expect
        # /usr/share/seclists need pointing at them.
        export SECLISTS="${pkgs.seclists}/share/seclists"
        export WORDLISTS="$SECLISTS"

        # Keep per-engagement state out of $HOME and out of the store.
        export ARSENAL_PROFILE="${name}"
        export ARSENAL_LOOT="''${ARSENAL_LOOT:-$PWD/loot}"
        mkdir -p "$ARSENAL_LOOT"

        ${mkBanner name}
      '';
    };

  # Shell for working on the repo itself, not for using the tools.
  devShell = pkgs.mkShellNoCC {
    name = "arsenal-dev";
    packages = with pkgs; [
      python3
      ruff
      nix-init
      nixpkgs-fmt
      deadnix
      statix
      nix-eval-jobs
      nix-fast-build
      jq
      git
    ];
    shellHook = ''
      export PYTHONPATH="$PWD/tools''${PYTHONPATH:+:$PYTHONPATH}"
      arsenal() { python3 -m arsenal.cli "$@"; }
      export -f arsenal 2>/dev/null || true
      echo "nix-arsenal dev shell -- ${toString catalog.count} catalog entries"
      echo "try: arsenal validate | arsenal coverage | arsenal missing --tier 2"
    '';
  };
}
