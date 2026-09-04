# Per-engagement toolset.
#
# The point of this template is not convenience -- it is that six months from
# now, when a finding is disputed, you can rebuild the exact toolchain that
# produced it. Commit flake.lock. Run `nix flake archive` before you start so
# the whole closure is on disk and a deleted upstream repo cannot invalidate
# your engagement mid-flight.
{
  description = "Toolset for ENGAGEMENT-NAME";

  inputs = {
    argos.url = "github:bry-lab/ArgosNix";
    # Pin to a revision, not a branch, once the engagement starts:
    # argos.url = "github:bry-lab/ArgosNix/COMMIT_SHA";
    nixpkgs.follows = "argos/nixpkgs";
  };

  outputs = { self, nixpkgs, argos }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ argos.overlays.default ];
      };
    in
    {
      devShells.${system}.default = pkgs.mkShellNoCC {
        name = "engagement";

        packages =
          argos.lib.select pkgs [ "recon" "web" "active-directory" ]
          ++ (with pkgs; [
            # Engagement-specific additions go here.
            jq
          ]);

        shellHook = ''
          export ENGAGEMENT="ENGAGEMENT-NAME"
          export ARGOS_LOOT="$PWD/loot"
          mkdir -p "$ARGOS_LOOT" notes
          echo "engagement shell: $ENGAGEMENT"
          echo "toolset pinned at ${self.inputs.argos.rev or "dirty"}"
        '';
      };
    };
}
