{
  description = "A complete NixOS VM, ready to use Argos";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    argos.url = "github:bry-lab/ArgosNix";
    # Keep Argos and this system on the same nixpkgs, so a tool you install with
    # `nix profile install .#<profile>` matches the system you built.
    argos.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, argos, ... }: {
    nixosConfigurations.argos-vm = nixpkgs.lib.nixosSystem {
      # aarch64-linux for Apple-silicon VMs (UTM on an M-series Mac).
      system = "x86_64-linux";
      modules = [
        argos.nixosModules.argos      # makes programs.argos available
        ./configuration.nix           # the full system config next to this file
        ./hardware-configuration.nix  # the file your installer generated -- keep it
      ];
    };
  };
}
