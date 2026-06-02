#!/usr/bin/env python3
"""
build_site.py — build the GitHub Pages search index + committed full text.

The site (index.html) is served from the repo ROOT so the PDFs and text/ are
reachable as siblings. Reads data/whitepapers.json and the cached pdftotext
output, then writes:
  search-index.json   compact metadata index (+ short snippet) for Fuse.js
  text/<name>.txt     committed plain text of every paper, so GitHub's own code
                      search indexes the whitepaper *contents*.

Run after tools/extract_metadata.py. No third-party deps.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = ROOT / "tools" / ".cache_txt"
TEXT = ROOT / "text"


def clean_snippet(text: str, n: int = 360) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t[:n]


def main() -> None:
    recs = json.loads((DATA / "whitepapers.json").read_text(encoding="utf-8"))
    TEXT.mkdir(exist_ok=True)

    index = []
    copied = 0
    for r in recs:
        cache_file = CACHE / (r["name"] + ".txt")
        snippet = ""
        if cache_file.exists():
            raw = cache_file.read_text(encoding="utf-8", errors="ignore")
            if raw.strip():
                snippet = clean_snippet(raw)
                # commit the plain text for GitHub-native full-text search
                (TEXT / (r["name"] + ".txt")).write_text(raw, encoding="utf-8")
                copied += 1
        wallets = []
        for v in r["wallets"].values():
            wallets.extend(v)
        # flattened, searchable string of platforms + handles (Fuse can't
        # traverse the nested socials object)
        social_text = " ".join(
            [p for p in r["socials"]] +
            [h for hs in r["socials"].values() for h in hs])
        index.append({
            "name": r["name"],
            "file": r["file"],
            "year": (r.get("dates") or {}).get("likely_year"),
            "team": r["people"]["team"][:6],
            "socials": r["socials"],
            "social_text": social_text,
            "wallets": wallets[:6],
            "snippet": snippet,
        })

    (ROOT / "search-index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    size = (ROOT / "search-index.json").stat().st_size
    print(f"Wrote search-index.json ({len(index)} records, {size//1024} KB)")
    print(f"Wrote text/ ({copied} plain-text files for GitHub full-text search)")


if __name__ == "__main__":
    main()
