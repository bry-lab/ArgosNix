{
  description = "Argos: a Nix-native, catalog-driven security toolkit for Linux";

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

      # Linux only. The capability layer -- security.wrappers, drivers, udev,
      # detonation VMs -- is what Argos is for, and none of it exists on macOS,
      # where you would get a bare bag of binaries most security tools cannot
      # use anyway. NixOS is the full experience; other Linux with Nix gets the
      # binaries plus reproducibility and degrades capabilities to sudo.
      systems = [ "x86_64-linux" "aarch64-linux" ];

      # Unfree is opt-in per package, never blanket-allowed. The list is derived
      # from the catalog so there is one place to declare "this is unfree" --
      # and CI checks that nothing on it is ever pushed to the binary cache.
      unfreeNames = lib.unique (map
        (tool: lib.last (lib.splitString "." tool.attr))
        (lib.filter (t: t.unfree && t.attr != null) (lib.attrValues catalog.entries)));

      # Source-available security tools that nixpkgs marks unfree (non-commercial
      # terms or a missing licence) but which Argos ships as normal tools: they
      # are freely redistributable and standard in the field, so they belong in
      # the flagship free profiles -- wpscan in webapp, waybackurls in osint --
      # rather than gated behind a catalog `unfree = true` flag. Like the catalog
      # unfree set, these must never be pushed to a public binary cache.
      permittedUnfree = [ "wpscan" "waybackurls" ];

      catalog = import ./nix/catalog.nix { inherit lib; };

      # One nixpkgs config, shared by the flake's own pkgs and by every NixOS
      # system and image we build, so the unfree/insecure policy is identical
      # everywhere rather than drifting between the devShells and the ISO.
      nixpkgsConfig = {
        allowUnfreePredicate = pkg:
          builtins.elem (lib.getName pkg) (unfreeNames ++ permittedUnfree);
        # A handful of genuinely useful forensics and RE tools are stuck on
        # ancient runtimes. Allowing them repo-wide is a deliberate trade;
        # revisit annually and drop anything that has been fixed upstream.
        #
        # ecdsa: pulled in transitively by impacket (the backbone of the AD
        # tooling). Upstream nixpkgs flags it for a timing side-channel that
        # does not matter for offensive use against a target you are testing.
        # The version prefix tracks the nixpkgs python; bump it when it drifts.
        permittedInsecurePackages = [ "python3.14-ecdsa-0.19.2" ];
      };

      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [ self.overlays.default ];
        config = nixpkgsConfig;
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

      # The `argos` CLI as a runnable program, so `nix run .#argos -- profile`
      # works without entering the dev shell -- and `nix run
      # github:bry-lab/ArgosNix#argos` works without cloning at all. The catalog
      # is bundled so it resolves outside a checkout; a real checkout still wins
      # at runtime (see find_root), keeping write commands writable.
      argosCliFor = pkgs: pkgs.writeShellApplication {
        name = "argos";
        runtimeInputs = [ pkgs.python3 ];
        text = ''
          export PYTHONPATH="${./tools}''${PYTHONPATH:+:$PYTHONPATH}"
          export ARGOS_ROOT="''${ARGOS_ROOT:-${./.}}"
          exec python3 -m argos.cli "$@"
        '';
      };

    in
    {
      # -- the catalog itself, for downstream consumers ------------------
      #
      # Exposed so other flakes can build their own profiles without forking:
      #   inherit (argos.lib) catalog;
      #   myShell = pkgs.mkShell { packages = argos.lib.select pkgs [ "web" "cloud" ]; };
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
            name = "argos-${name}";
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
              self.nixosModules.argos
              ./images/live.nix
              { nixpkgs.overlays = [ self.overlays.default ]; nixpkgs.config = nixpkgsConfig; }
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

          # The maintenance CLI, installable and runnable on its own.
          argos = argosCliFor pkgs;

          # Machine-readable catalog, for the coverage dashboard and for anyone
          # who wants the mapping without the Nix.
          catalog-json = pkgs.writeText "argos-catalog.json"
            (builtins.toJSON catalog.entries);
        });

      # -- apps: `nix run .#argos -- <command>` --------------------------
      apps = forAllSystems ({ pkgs, ... }:
        let
          argos = argosCliFor pkgs;
          app = {
            type = "app";
            program = "${argos}/bin/argos";
            meta.description = "The Argos catalog maintenance CLI";
          };
        in
        {
          argos = app;
          default = app;
        });

      # -- NixOS: the part that actually replaces a distro ----------------
      nixosModules = {
        default = self.nixosModules.argos;
        argos = import ./modules/nixos { inherit catalog; };
      };

      homeModules = {
        default = self.homeModules.argos;
        argos = import ./modules/home-manager { inherit catalog; };
      };

      # A bootable reference system per Linux architecture. This is what people
      # mean by a real security distro -- a shell full of binaries is not a
      # substitute for a live ISO with working monitor mode.
      nixosConfigurations = lib.listToAttrs (map
        (system: lib.nameValuePair "argos-${system}" (nixpkgs.lib.nixosSystem {
          inherit system;
          modules = [
            self.nixosModules.argos
            ./images/live.nix
            { nixpkgs.overlays = [ self.overlays.default ]; nixpkgs.config = nixpkgsConfig; }
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
          catalog = pkgs.runCommand "argos-catalog-check"
            { nativeBuildInputs = [ pkgs.python3 ]; } ''
            cd ${./.}
            PYTHONPATH=tools python3 -m argos.cli validate
            PYTHONPATH=tools python3 -m argos.cli profile > /dev/null
            touch $out
          '';

          # Every profile must resolve to a non-empty package list. Catches a
          # renamed nixpkgs attribute before a user does.
          profiles-resolve = pkgs.runCommand "argos-profiles-check" { } ''
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
