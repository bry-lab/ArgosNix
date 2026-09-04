"""Argos catalog tooling.

The catalog is the source of truth; the flake is generated from it. If you are
about to hand-edit a package list in a .nix file, stop -- edit catalog/tools/
instead and let nix/profiles.nix do the assembling.
"""

__version__ = "0.1.0"
