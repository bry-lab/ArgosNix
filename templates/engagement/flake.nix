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
    arsenal.url = "github:OWNER/nix-arsenal";
    # Pin to a revision, not a branch, once the engagement starts:
    # arsenal.url = "github:OWNER/nix-arsenal/COMMIT_SHA";
    nixpkgs.follows = "arsenal/nixpkgs";
  };

  outputs = { self, nixpkgs, arsenal }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ arsenal.overlays.default ];
      };
    in
    {
      devShells.${system}.default = pkgs.mkShellNoCC {
        name = "engagement";

        packages =
          arsenal.lib.select pkgs [ "recon" "web" "active-directory" ]
          ++ (with pkgs; [
            # Engagement-specific additions go here.
            jq
          ]);

        shellHook = ''
          export ENGAGEMENT="ENGAGEMENT-NAME"
          export ARSENAL_LOOT="$PWD/loot"
          mkdir -p "$ARSENAL_LOOT" notes
          echo "engagement shell: $ENGAGEMENT"
          echo "toolset pinned at ${self.inputs.arsenal.rev or "dirty"}"
        '';
      };
    };
}
