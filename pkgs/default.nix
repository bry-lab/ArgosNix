# Derivations for tools nixpkgs does not have (yet).
#
# by-name/<tool>/package.nix is discovered automatically -- adding a package is
# one directory and one file, no registry to edit. The directory name must match
# the catalog id and the catalog entry's `local` field, and `argos validate`
# enforces that.
#
# POLICY: anything here that is broadly useful should be upstreamed to nixpkgs
# and then demoted to tier 1. This directory is a staging area and a home for
# the long tail, not a parallel nixpkgs. Owning 2,500 derivations forever is how
# this project dies; see docs/UPSTREAMING.md.
{ lib, callPackage }:

let
  dir = ./by-name;

  entries = lib.filterAttrs
    (name: type: type == "directory" && builtins.pathExists (dir + "/${name}/package.nix"))
    (if builtins.pathExists dir then builtins.readDir dir else { });

in
lib.mapAttrs (name: _: callPackage (dir + "/${name}/package.nix") { }) entries
