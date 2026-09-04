"""Tests for the two things that must not break.

Run: cd tools && python3 -m unittest discover tests

1. Identity normalisation. If this is wrong the catalog silently accumulates
   duplicates or silently merges unrelated tools, and neither is visible until
   somebody notices a profile is missing something.

2. The upsert invariant: importers may only fill blanks and extend provenance.
   If this breaks, running an importer quietly destroys hand curation, and since
   importers run nightly you would lose weeks of work before noticing.
"""

import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argos.catalog import Catalog, Tool  # noqa: E402
from argos.identity import normalise, shard_for, slugify  # noqa: E402


class TestIdentity(unittest.TestCase):
    def test_github_forms_collapse(self):
        variants = [
            "https://github.com/ProjectDiscovery/Nuclei",
            "https://github.com/projectdiscovery/nuclei.git",
            "http://www.github.com/projectdiscovery/nuclei/",
            "git@github.com:projectdiscovery/nuclei.git",
            "github.com/projectdiscovery/nuclei",
            "https://github.com/projectdiscovery/nuclei/tree/main/v3",
            "https://github.com/projectdiscovery/nuclei/releases",
        ]
        urls = {normalise(v).url for v in variants}
        self.assertEqual(urls, {"https://github.com/projectdiscovery/nuclei"})

    def test_github_pages_maps_to_repo(self):
        self.assertEqual(
            normalise("https://ly4k.github.io/Certipy").url,
            "https://github.com/ly4k/certipy",
        )

    def test_distinct_repos_stay_distinct(self):
        a = normalise("https://github.com/sullo/nikto")
        b = normalise("https://github.com/OJ/gobuster")
        self.assertNotEqual(a.url, b.url)

    def test_non_forge_url_is_preserved(self):
        got = normalise("https://www.cgsecurity.org/wiki/TestDisk/")
        self.assertEqual(got.url, "https://cgsecurity.org/wiki/TestDisk")
        self.assertIsNone(got.forge)

    def test_missing_upstream_is_synthetic_not_dropped(self):
        got = normalise(None, fallback="Some Weird Tool")
        self.assertTrue(got.is_synthetic)
        self.assertEqual(got.url, "urn:name:some-weird-tool")

    def test_slugify(self):
        self.assertEqual(slugify("Name-That-Hash"), "name-that-hash")
        self.assertEqual(slugify("THC Hydra"), "thc-hydra")
        self.assertEqual(slugify("  __weird__  "), "weird")

    def test_shard(self):
        self.assertEqual(shard_for("nmap"), "n")
        self.assertEqual(shard_for("7zip"), "0")


def _tool(**kw):
    base = dict(id="nuclei", upstream="https://github.com/projectdiscovery/nuclei",
                categories=["web"], tier=1, nixpkgs="nuclei")
    base.update(kw)
    return Tool(**base)


class TestUpsertInvariant(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog()
        self.cat.tools["nuclei"] = _tool(
            description="Curated description we wrote by hand.",
            categories=["web", "recon"],
            provenance={"kali": "nuclei"},
        )

    def test_importer_cannot_overwrite_curation(self):
        incoming = _tool(
            description="Auto-scraped description.",
            tier=3,
            nixpkgs=None,
            provenance={"blackarch": "nuclei"},
        )
        tool, action = self.cat.upsert(incoming, source="blackarch")
        self.assertEqual(action, "merged")
        self.assertEqual(tool.description, "Curated description we wrote by hand.")
        self.assertEqual(tool.tier, 1)
        self.assertEqual(tool.nixpkgs, "nuclei")

    def test_importer_extends_provenance(self):
        incoming = _tool(provenance={"blackarch": "nuclei"})
        tool, _ = self.cat.upsert(incoming, source="blackarch")
        self.assertEqual(tool.provenance, {"kali": "nuclei", "blackarch": "nuclei"})

    def test_matches_on_upstream_despite_renamed_package(self):
        """The whole point: a distro renaming a package must not create a dupe."""
        incoming = Tool(
            id="nuclei-scanner",
            upstream="https://github.com/ProjectDiscovery/Nuclei.git",
            categories=["web"],
            tier=3,
            provenance={"blackarch": "nuclei-scanner"},
        )
        _, action = self.cat.upsert(incoming, source="blackarch")
        self.assertEqual(action, "merged")
        self.assertEqual(len(self.cat), 1)
        self.assertIn("nuclei-scanner", self.cat.tools["nuclei"].aliases)

    def test_matches_on_alias_when_upstream_unknown(self):
        self.cat.tools["netexec"] = Tool(
            id="netexec", upstream="https://github.com/Pennyw0rth/NetExec",
            categories=["active-directory"], tier=1, nixpkgs="netexec",
            aliases=["crackmapexec"],
        )
        incoming = Tool(id="crackmapexec", upstream="urn:name:crackmapexec",
                        categories=["active-directory"], tier=3,
                        provenance={"remnux": "crackmapexec"})
        _, action = self.cat.upsert(incoming, source="remnux")
        self.assertEqual(action, "merged")
        self.assertEqual(len(self.cat), 2)

    def test_genuinely_new_tool_is_added(self):
        incoming = Tool(id="ffuf", upstream="https://github.com/ffuf/ffuf",
                        categories=["web"], tier=3)
        _, action = self.cat.upsert(incoming, source="blackarch")
        self.assertEqual(action, "added")
        self.assertEqual(len(self.cat), 2)

    def test_reimport_is_idempotent(self):
        incoming = _tool(provenance={"blackarch": "nuclei"})
        self.cat.upsert(incoming, source="blackarch")
        _, action = self.cat.upsert(incoming, source="blackarch")
        self.assertEqual(action, "unchanged")

    def test_category_cap_is_respected(self):
        self.cat.tools["nuclei"].categories = ["web", "recon", "osint", "defense"]
        incoming = _tool(categories=["cloud"])
        tool, _ = self.cat.upsert(incoming, source="kali")
        self.assertEqual(len(tool.categories), 4)


class TestValidation(unittest.TestCase):
    CATS = ["web", "recon"]

    def test_duplicate_upstream_is_an_error(self):
        cat = Catalog()
        cat.tools["a"] = _tool(id="a")
        cat.tools["b"] = _tool(id="b", nixpkgs="other")
        errors = cat.validate(self.CATS)
        self.assertTrue(any("shares upstream" in e for e in errors))

    def test_tier_one_needs_an_attribute(self):
        cat = Catalog()
        cat.tools["a"] = _tool(id="a", nixpkgs=None)
        errors = cat.validate(self.CATS)
        self.assertTrue(any("tier 1 requires" in e for e in errors))

    def test_tier_four_must_not_claim_a_package(self):
        cat = Catalog()
        cat.tools["a"] = _tool(id="a", tier=4, nixpkgs=None, local="a")
        errors = cat.validate(self.CATS)
        self.assertTrue(any("tier 4" in e for e in errors))

    def test_unknown_category_is_an_error(self):
        cat = Catalog()
        cat.tools["a"] = _tool(id="a", categories=["nonsense"])
        errors = cat.validate(self.CATS)
        self.assertTrue(any("unknown category" in e for e in errors))


class TestRoundTrip(unittest.TestCase):
    def test_real_catalog_survives_save_and_load(self):
        root = Path(__file__).resolve().parents[2]
        original = Catalog.load(root)
        self.assertGreater(len(original), 0, "seed catalog is missing")

        import tempfile, shutil  # noqa: E401

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "catalog").mkdir()
            shutil.copy(root / "catalog" / "taxonomy.toml", tmp_root / "catalog")
            original.save(tmp_root)
            reloaded = Catalog.load(tmp_root)

        self.assertEqual(len(original), len(reloaded))
        for tool_id, tool in original.tools.items():
            self.assertEqual(tool.to_dict(), reloaded.tools[tool_id].to_dict())


if __name__ == "__main__":
    unittest.main()
