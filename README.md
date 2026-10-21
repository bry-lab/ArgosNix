## WIP

# ArgosNix

A catalog of security tools, organized by what you're trying to do and delivered
as Nix profiles you can install anywhere.

```sh
nix develop github:bry-lab/ArgosNix#osint      # or #webapp, #ad, #dfir, #malware…
nix profile add github:bry-lab/ArgosNix#network
nix build github:bry-lab/ArgosNix#iso          # a live system, not just a shell
```

## Quick Start

0. Install Nix on your distribution of choice (see [Installing Nix](#installing-nix)). Skip to step 1 if you're on a NixOS machine.
1. To install a profile that persists across shells and reboots, run:

   ```sh
   nix profile add github:bry-lab/ArgosNix#<profile>
   ```

   Or, to try a profile in a throwaway shell that leaves nothing behind:

   ```sh
   nix develop github:bry-lab/ArgosNix#<profile>
   ```

2. To check which profiles and packages are currently installed:

   ```sh
   nix profile list
   ```

3. To offload a profile, using its name from the list:

   ```sh
   nix profile remove <profile>
   ```

**Note:** offloading a profile does not free up disk space on its own. Nix keeps
old profile versions around for rollbacks. To reclaim the space, clear out
history older than 7 days (recommended), then collect the unused files:

```sh
nix profile wipe-history --older-than 7d
nix store gc
```

**Available profiles:** `osint`, `webapp`, `network`, `ad`, `wireless`, `radio`, `redteam`, `malware`,
`revuln`, `dfir`, `cloud`, `mobile`, `crypto`, `defense`, `ctf`, `full`

To see what a profile contains, including any tools not yet packaged:

```sh
nix run github:bry-lab/ArgosNix#argos -- profile <profile> --all
```

## Status — read this before relying on it

See [docs/COVERAGE.md](docs/COVERAGE.md), which is regenerated nightly:

- Every tool in the catalog is mapped to its upstream and deduplicated by where
  the code lives. That mapping is useful on its own.
- The rest is a packaging backlog, tiered by difficulty. `argos missing --tier 2`
  is the contributor queue.
- Some tools will Burp Pro, Cobalt Strike, Nessus and friends are licensed and not 
- redistributable therefore, they will not be included in ArgosNix. They are catalogued as tier 4 with a note,
  so the coverage number stays honest.

## Nix and NixOS Background Information

Nix is a package manager that can be installed on any Linux distribution as well
as macOS and WSL. NixOS is a Linux distribution built on top of the Nix package
manager, much like how Debian Linux is built on top of `dpkg` and `apt`. Nix's
core functionality goes much further than being just a package manager; it can
even declaratively define whole system configurations.

Every nix command works the same on any machine with Nix installed and flakes 
enabled and nothing here uses your system package manager. A machine running 
Ubuntu, Debian, Fedora, Arch, or WSL2 gets the same tools at the same versions as a
native NixOS machine. The one difference is privileges, covered in
[The capability problem](#the-capability-problem).

### Installing Nix

If Nix isn't installed yet, pick one:

```sh
# Determinate Systems installer — recommended, enables flakes out of the box:
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

# ...or the official installer, then enable flakes yourself:
sh <(curl -L https://nixos.org/nix/install) --daemon
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
```

Open a new shell after installing, and you're ready.

This README uses `nix profile add`, the current name for what older Nix versions
call `nix profile install`. If `add` isn't recognized, use `install` instead, or
update Nix.

## How ArgosNix is organized

```
catalog/          toml files that lists and/or organizes the tools
  tools/*.toml    tools listed out in toml files in alphabetical order
  taxonomy.toml   ~20 categories, ours, mapped from upstream groups
  profiles.toml   what each profile contains
nix/              reads the catalog, generates everything
pkgs/by-name/     derivations for tools nixpkgs lacks
modules/          NixOS + home-manager: capabilities, drivers, udev
images/           live ISO / VM / qcow definitions
tools/argos/      the CLI: importers, validation, coverage
templates/        per-engagement scaffold
examples/         ready-to-copy configs (a full VM system, and a module)
```

### Categories vs profiles

Categories are how the catalog is organized (`web`, `active-directory`,
`malware-analysis`, etc). Profiles are how you use it (Ex: `osint`, `webapp`, `network`, 
`ad`, `wireless`, `radio`, `redteam`, `malware`, `revuln`, `dfir`, `cloud`, `mobile`, `crypto`, 
`defense`, `ctf`, `full`). A profile is composed of one or more categories, so OSINT and web testing 
share their recon tooling instead of two lists drifting apart.

```sh
nix run .#argos -- profile              # every profile and its coverage
nix run .#argos -- profile ad --all     # what is in it, including gaps
```

## Using it: load and offload a package set

A "package set" is a profile. Loading one means putting its tools on your `PATH`;
offloading means taking them back off. Nothing is ever installed globally unless
you ask for it.

```sh
# Peek before you load — what is in a set, and what (if anything) is missing:
nix run github:bry-lab/ArgosNix#argos -- profile dfir --all

# Load into a throwaway shell. Nothing touches your system; the tools are on
# PATH only inside this shell:
nix develop github:bry-lab/ArgosNix#dfir
#   ...work with the forensics tools...
exit                     # offload — your PATH is clean again, system untouched
```

Rule of thumb: use the throwaway shell for a session, and `nix profile` (below)
when you want tools to stick around. Replace the `github:bry-lab/ArgosNix` prefix
with `.` when you are inside a local clone (`nix develop .#dfir`).

### Keeping tools around: `nix profile` as a package manager

If you want tools installed the way a normal package manager installs them,
persistent across shells and reboots until you remove them, use `nix profile`.

```sh
# add (load): stays until you remove it
nix profile add github:bry-lab/ArgosNix#revuln
nix profile add nixpkgs#nmap nixpkgs#gdb nixpkgs#ghidra

# whole Argos sets stack and de-duplicate against each other
nix profile add github:bry-lab/ArgosNix#osint github:bry-lab/ArgosNix#webapp

nix profile list             # see what's installed
nix profile remove ghidra    # remove (offload) one, by name from the list
nix profile upgrade --all    # update everything to the latest
nix profile rollback         # undo the last change if something breaks
```

One catch: removing a tool does not free disk space immediately. Nix keeps a
history of old profile versions for rollbacks, and the store's automatic cleanup
will not touch anything still referenced by that history.

To actually reclaim the space:

```sh
nix profile wipe-history --older-than 7d   # drop old profile generations
nix store gc                               # then collect the now-unused paths
```

## The capability problem

A devShell can put `nmap` on your PATH. It cannot give it `CAP_NET_RAW`, load a
monitor-mode driver, or write a udev rule for your Proxmark. That was always the
real value of a security distro, and a flake alone does not replace it.

So each catalog entry declares what privileges it needs, and the NixOS module
turns that into `security.wrappers`, driver selection and udev rules
automatically:

```nix
programs.argos = {
  enable = true;
  profiles = [ "network" "ad" "wireless" ];
  users = [ "you" ];
  hardware.wireless = true;
  hardware.sdr = true;
};
```

On non-NixOS Linux you get the binaries and not the capabilities; grant them
yourself with `sudo` or `setcap` where needed. The shell tells you which tools
are affected rather than letting you find out mid-engagement.

Two ready-made configs ship with the repo:

- [examples/nixos-vm/](examples/nixos-vm/) — a **complete drop-in system** for a
  fresh NixOS VM. Copy two files in, keep your generated
  `hardware-configuration.nix`, `nixos-rebuild switch`, then
  `nix profile add …#<profile>` per use case.
- [examples/configuration.nix](examples/configuration.nix) — a **partial module**
  to compose into an existing system you already run.

### Fresh NixOS VM, start to finish

```sh
cd /etc/nixos
# back up the generated config first; it holds your stateVersion
sudo cp configuration.nix configuration.nix.bak

# copy the two files in (keep your generated hardware-configuration.nix)
sudo curl -L -O https://raw.githubusercontent.com/bry-lab/ArgosNix/main/examples/nixos-vm/flake.nix
sudo curl -L -O https://raw.githubusercontent.com/bry-lab/ArgosNix/main/examples/nixos-vm/configuration.nix

# edit configuration.nix: set your username, and copy system.stateVersion
# from configuration.nix.bak
sudo nixos-rebuild switch --flake /etc/nixos#argos-vm

# then install tools per use case, and offload them when done:
nix profile add github:bry-lab/ArgosNix#revuln
nix profile add github:bry-lab/ArgosNix#osint
nix profile remove osint          # offload one, keep the rest
```

Keep the `hardware-configuration.nix` the installer generated, it holds your
disk layout and is the one file the repo cannot ship for you.

## Scope and legality

All tools in ArgosNix are publically availiable and the project is solely packaging them in 
one place that is easy to load and offload. Use it against systems you are authorized to test. 
Licensed commercial software is cataloged but never redistributed.
