{
  description = "A complete NixOS VM, ready to use Argos";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    argos.url = "github:bry-lab/ArgosNix";
    # Keep Argos and this system on the same nixpkgs, so a tool you install with
    # `nix profile add .#<profile>` matches the system you built.
    argos.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, argos, ... }:
    let
      mkVm = system: nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          argos.nixosModules.argos      # makes programs.argos available
          ./configuration.nix           # the full system config next to this file
          ./hardware-configuration.nix  # the file your installer generated -- keep it
        ];
      };
    in
    {
      nixosConfigurations = {
        # Intel/AMD VMs:   nixos-rebuild switch --flake /etc/nixos#argos-vm
        argos-vm = mkVm "x86_64-linux";
        # ARM VMs (e.g. UTM on an M-series Mac):
        #                  nixos-rebuild switch --flake /etc/nixos#argos-vm-aarch64
        argos-vm-aarch64 = mkVm "aarch64-linux";
      };
    };
}
