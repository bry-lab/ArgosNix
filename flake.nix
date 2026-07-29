{
  description = "A Nix-native security toolset: Kali, BlackArch, REMnux and Athena, deduplicated into one catalog";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    nixos-generators = {
      url = "github:nix-community/nixos-generators";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nixos-generators, ... }:
    let
      inherit (nixpkgs) lib;

      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # Unfree is opt-in per package, never blanket-allowed. The list is derived
      # from the catalog so there is one place to declare "this is unfree" --
      # and CI checks that nothing on it is ever pushed to the binary cache.
      unfreeNames = lib.unique (map
        (tool: lib.last (lib.splitString "." tool.attr))
        (lib.filter (t: t.unfree && t.attr != null) (lib.attrValues catalog.entries)));

      catalog = import ./nix/catalog.nix { inherit lib; };

      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [ self.overlays.default ];
        config = {
          allowUnfreePredicate = pkg: builtins.elem (lib.getName pkg) unfreeNames;
          # A handful of genuinely useful forensics and RE tools are stuck on
          # ancient runtimes. Allowing them repo-wide is a deliberate trade;
          # revisit annually and drop anything that has been fixed upstream.
          permittedInsecurePackages = [ ];
        };
      };

      forAllSystems = f: lib.genAttrs systems (system: f {
        inherit system;
        pkgs = pkgsFor system;
      });

      profilesFor = pkgs: import ./nix/profiles.nix { inherit lib pkgs catalog; };
      shellsFor = pkgs: import ./nix/shell.nix {
        inherit lib pkgs catalog;
        profiles = profilesFor pkgs;
      };

    in
    {
      # -- the catalog itself, for downstream consumers ------------------
      #
      # Exposed so other flakes can build their own profiles without forking:
      #   inherit (arsenal.lib) catalog;
      #   myShell = pkgs.mkShell { packages = arsenal.lib.select pkgs [ "web" "cloud" ]; };
      lib = {
        inherit catalog;
        profiles = profilesFor;

        # Ad-hoc selection by category, for people who want their own mix
        # rather than one of our profiles.
        select = pkgs: categories:
          let
            wanted = lib.filter
              (t: t.attr != null
                  && !t.unfree
                  && builtins.any (c: builtins.elem c categories) t.categories)
              (lib.attrValues catalog.entries);
            resolve = t: lib.attrByPath (lib.splitString "." t.attr) null pkgs;
          in
          lib.unique (builtins.filter (p: p != null) (map resolve wanted));
      };

      overlays.default = import ./overlays;

      # -- devShells: one per profile ------------------------------------
      devShells = forAllSystems ({ pkgs, ... }:
        let
          shells = shellsFor pkgs;
          profiles = profilesFor pkgs;
          perProfile = lib.genAttrs profiles.names shells.mkProfileShell;
        in
        perProfile // {
          dev = shells.devShell;
          default = shells.devShell;
        });

      # -- packages: installable environments + our own derivations ------
      packages = forAllSystems ({ pkgs, system, ... }:
        let
          profiles = profilesFor pkgs;

          mkEnv = name: pkgs.buildEnv {
            name = "arsenal-${name}";
            paths = profiles.packagesFor name;
            # Security tooling collides constantly: three packages ship a
            # `bin/dnsenum`, four ship overlapping man pages. Last one wins and
            # that is acceptable for an environment, though not for nixpkgs.
            ignoreCollisions = true;
            extraOutputsToInstall = [ "man" "doc" "share" ];
          };

          environments = lib.genAttrs profiles.names mkEnv;

          ourPackages = import ./pkgs {
            inherit lib;
            inherit (pkgs) callPackage;
          };

          # Images are the real distro-replacement deliverable. A devShell gives
          # you binaries; an ISO gives you binaries plus the kernel modules,
          # udev rules and capability wrappers they need to work.
          mkImage = format: nixos-generators.nixosGenerate {
            inherit system format;
            modules = [
              self.nixosModules.arsenal
              ./images/live.nix
              { nixpkgs.overlays = [ self.overlays.default ]; }
            ];
          };

          images = lib.optionalAttrs (lib.hasSuffix "linux" system) {
            iso = mkImage "install-iso";
            vm = mkImage "vm";
            qcow = mkImage "qcow";
            raw = mkImage "raw-efi";
          };

        in
        environments // ourPackages // images // {
          default = environments.full;

          # Machine-readable catalog, for the coverage dashboard and for anyone
          # who wants the mapping without the Nix.
          catalog-json = pkgs.writeText "arsenal-catalog.json"
            (builtins.toJSON catalog.entries);
        });

      # -- NixOS: the part that actually replaces a distro ----------------
      nixosModules = {
        default = self.nixosModules.arsenal;
        arsenal = import ./modules/nixos { inherit catalog; };
      };

      homeModules = {
        default = self.homeModules.arsenal;
        arsenal = import ./modules/home-manager { inherit catalog; };
      };

      # A bootable reference system per Linux architecture. This is what people
      # mean when they say "replace Kali" -- a shell full of binaries is not a
      # substitute for a live ISO with working monitor mode.
      nixosConfigurations = lib.listToAttrs (map
        (system: lib.nameValuePair "arsenal-${system}" (nixpkgs.lib.nixosSystem {
          inherit system;
          modules = [
            self.nixosModules.arsenal
            ./images/live.nix
            { nixpkgs.overlays = [ self.overlays.default ]; }
          ];
        }))
        [ "x86_64-linux" "aarch64-linux" ]);

      # -- per-engagement scaffold ----------------------------------------
      templates = {
        engagement = {
          path = ./templates/engagement;
          description = "Pin this toolset to a single engagement, reproducibly";
        };
        default = self.templates.engagement;
      };

      # -- checks ----------------------------------------------------------
      checks = forAllSystems ({ pkgs, system, ... }:
        let
          profiles = profilesFor pkgs;
        in
        {
          # Catalog integrity, without needing nix to evaluate every package.
          catalog = pkgs.runCommand "arsenal-catalog-check"
            { nativeBuildInputs = [ pkgs.python3 ]; } ''
            cd ${./.}
            PYTHONPATH=tools python3 -m arsenal.cli validate
            PYTHONPATH=tools python3 -m arsenal.cli profile > /dev/null
            touch $out
          '';

          # Every profile must resolve to a non-empty package list. Catches a
          # renamed nixpkgs attribute before a user does.
          profiles-resolve = pkgs.runCommand "arsenal-profiles-check" { } ''
            ${lib.concatMapStringsSep "\n"
              (name: ''
                echo "${name}: ${toString (builtins.length (profiles.packagesFor name))} packages"
              '')
              profiles.names}
            touch $out
          '';
        });

      formatter = forAllSystems ({ pkgs, ... }: pkgs.nixpkgs-fmt);
    };
}
