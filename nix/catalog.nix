# Load the TOML catalog into Nix.
#
# No import-from-derivation, no generated .nix files checked in. `builtins.fromTOML`
# reads the same files the Python tooling writes, so there is exactly one source
# of truth and no generation step to forget to run.
#
# Cost: evaluating a few thousand entries adds roughly a second to `nix flake
# show`. Worth it. If it ever stops being worth it, the fix is a build-time
# `arsenal export --json` behind an IFD, not hand-maintained Nix lists.
{ lib }:

let
  toolsDir = ../catalog/tools;

  shards = lib.filterAttrs
    (name: type: type == "regular" && lib.hasSuffix ".toml" name)
    (builtins.readDir toolsDir);

  readShard = name: builtins.fromTOML (builtins.readFile (toolsDir + "/${name}"));

  tools = lib.foldl' (acc: name: acc // readShard name) { }
    (lib.attrNames shards);

  taxonomy = builtins.fromTOML (builtins.readFile ../catalog/taxonomy.toml);
  profiles = builtins.fromTOML (builtins.readFile ../catalog/profiles.toml);

  # Normalise optional fields once, so consumers never write `x.y or default`.
  normalise = id: raw: {
    inherit id;
    upstream = raw.upstream;
    description = raw.description or null;
    license = raw.license or null;
    categories = raw.categories or [ ];
    tier = raw.tier or 3;
    nixpkgs = raw.nixpkgs or null;
    local = raw.local or null;
    builder = raw.builder or null;
    unfree = raw.unfree or false;
    platforms = raw.platforms or null;
    capabilities = raw.capabilities or [ ];
    alternatives = raw.alternatives or [ ];
    aliases = raw.aliases or [ ];
    status = raw.status or "active";
    notes = raw.notes or null;
    provenance = raw.provenance or { };

    # The attribute that provides this tool, or null if nothing does yet.
    attr = raw.nixpkgs or raw.local or null;
  };

in
rec {
  inherit taxonomy profiles;

  entries = lib.mapAttrs normalise tools;

  ids = lib.attrNames entries;

  count = builtins.length ids;

  byCategory = category:
    lib.filterAttrs (_: tool: builtins.elem category tool.categories) entries;

  packaged = lib.filterAttrs (_: tool: tool.attr != null) entries;

  # Tools that need privileges a devShell cannot grant. modules/nixos consumes
  # this to decide what to wrap.
  needingCapability = capability:
    lib.filterAttrs (_: tool: builtins.elem capability tool.capabilities) entries;

  allCapabilities = lib.unique
    (lib.concatMap (tool: tool.capabilities) (lib.attrValues entries));
}
