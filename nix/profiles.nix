# Turn catalog entries + profile definitions into concrete package lists.
#
# This mirrors tools/arsenal/profiles.py. Keep them in step: the `profiles-resolve`
# flake check evaluates every profile here, and the `catalog` check runs the
# Python path, so a divergence shows up as one of them failing.
#
# The one deliberate divergence: the Python side lists unpackaged tools so it
# can report gaps, whereas here they are dropped. A null attribute is an
# evaluation error, not a warning, and a profile that fails to evaluate because
# somebody added a catalog entry without a derivation would be miserable.
{ lib, pkgs, catalog }:

let
  inherit (lib) attrByPath splitString filterAttrs attrValues concatMap unique;

  defaultTiers = [ 1 2 3 ];

  resolveAttr = attr:
    let path = splitString "." attr;
    in attrByPath path null pkgs;

  # A tool contributes a package only if its attribute actually exists. Missing
  # attributes are collected rather than thrown so `arsenal`/CI can report them.
  toPackage = tool:
    if tool.attr == null then null else resolveAttr tool.attr;

  normaliseProfile = name: raw: {
    inherit name;
    description = raw.description or "";
    categories = raw.categories or [ ];
    extra = raw.extra or [ ];
    exclude = raw.exclude or [ ];
    tiers = raw.tiers or defaultTiers;
    unfree = raw.unfree or false;
    wildcard = builtins.elem "*" (raw.categories or [ ]);
  };

  profiles = lib.mapAttrs normaliseProfile catalog.profiles;

  selectTools = profile:
    let
      inScope = tool:
        !(builtins.elem tool.id profile.exclude)
        && builtins.elem tool.tier profile.tiers
        && (profile.unfree || !tool.unfree)
        && tool.status != "superseded"
        && (profile.wildcard
            || builtins.any (c: builtins.elem c profile.categories) tool.categories);

      selected = filterAttrs (_: inScope) catalog.entries;

      extras = lib.getAttrs
        (builtins.filter (id: catalog.entries ? ${id}) profile.extra)
        catalog.entries;
    in
    selected // extras;

in
rec {
  inherit profiles;

  names = lib.attrNames profiles;

  # Every tool a profile wants, including ones with no package yet.
  toolsFor = name: attrValues (selectTools profiles.${name});

  # Catalog ids the profile wants but cannot supply. Surfaced in the shell
  # banner so users are never silently missing something they expected.
  missingFor = name:
    map (t: t.id)
      (builtins.filter (t: toPackage t == null) (toolsFor name));

  packagesFor = name:
    unique (builtins.filter (p: p != null) (map toPackage (toolsFor name)));

  # Capabilities the profile's tools need. Drives the devShell warning and the
  # NixOS module's wrapper set.
  capabilitiesFor = name:
    unique (concatMap (t: t.capabilities)
      (builtins.filter (t: toPackage t != null) (toolsFor name)));

  statsFor = name:
    let
      wanted = toolsFor name;
      missing = missingFor name;
    in
    {
      wanted = builtins.length wanted;
      available = builtins.length wanted - builtins.length missing;
      missing = builtins.length missing;
    };
}
