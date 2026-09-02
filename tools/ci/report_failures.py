#!/usr/bin/env python3
"""Turn nix-fast-build results into a markdown failure report.

A catalog this size will always have some percentage broken -- upstream repos
vanish, hashes rot, Python 2 tools finally stop building. The goal is not zero
failures, it is a visible, shrinking list that nobody is surprised by.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main(path: str) -> int:
    try:
        results = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read results: {exc}", file=sys.stderr)
        return 1

    failed = [r for r in results.get("results", []) if not r.get("success")]
    total = len(results.get("results", []))

    print(f"## Build report\n")
    print(f"{total - len(failed)}/{total} succeeded.\n")

    if not failed:
        print("No failures.")
        return 0

    by_reason: dict[str, list[str]] = defaultdict(list)
    for item in failed:
        reason = (item.get("error") or "unknown").splitlines()[0][:120]
        by_reason[reason].append(item.get("attr", "?"))

    print("| Failure | Count | Packages |")
    print("| --- | ---: | --- |")
    for reason, attrs in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        shown = ", ".join(f"`{a}`" for a in sorted(attrs)[:8])
        more = f" +{len(attrs) - 8} more" if len(attrs) > 8 else ""
        print(f"| {reason} | {len(attrs)} | {shown}{more} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "results.json"))
