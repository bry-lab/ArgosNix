# ENGAGEMENT-NAME

```sh
nix develop          # or: direnv allow
```

Before starting:

```sh
nix flake lock                 # pin everything
nix flake archive              # fetch the full closure locally
git add flake.lock && git commit -m "pin toolset"
```

`loot/` is gitignored on purpose. Put client data there and nowhere else.
