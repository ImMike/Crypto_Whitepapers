#!/usr/bin/env python3
"""
search.py — full-text + metadata search across the whitepaper archive, offline.

Examples:
  python tools/search.py "proof of stake"        # full text of every paper
  python tools/search.py --wallet 0x49aec0        # find a wallet address
  python tools/search.py --team Terpin            # find a person
  python tools/search.py --social telegram        # papers linking Telegram
  python tools/search.py "staking" --year 2017    # combine text + year filter

Searches text/ (committed) if present, else tools/.cache_txt/. No deps.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEXT = ROOT / "text"
CACHE = ROOT / "tools" / ".cache_txt"

GREEN, ORANGE, DIM, RST = "\033[32m", "\033[33m", "\033[2m", "\033[0m"


def text_dir() -> Path:
    return TEXT if TEXT.exists() and any(TEXT.iterdir()) else CACHE


def main() -> None:
    ap = argparse.ArgumentParser(description="Search the crypto whitepaper archive.")
    ap.add_argument("query", nargs="?", help="full-text search phrase")
    ap.add_argument("--wallet", help="match a wallet/contract address substring")
    ap.add_argument("--team", help="match a team/founder name")
    ap.add_argument("--social", help="match a social platform (telegram, github, ...)")
    ap.add_argument("--year", type=int, help="filter by likely publication year")
    ap.add_argument("-n", "--limit", type=int, default=40, help="max results")
    args = ap.parse_args()

    recs = json.loads((DATA / "whitepapers.json").read_text(encoding="utf-8"))
    by_name = {r["name"]: r for r in recs}
    tdir = text_dir()
    rx = re.compile(re.escape(args.query), re.I) if args.query else None

    hits = []
    for r in recs:
        if args.year and (r.get("dates") or {}).get("likely_year") != args.year:
            continue
        if args.wallet:
            allw = [a for v in r["wallets"].values() for a in v]
            if not any(args.wallet.lower() in a.lower() for a in allw):
                continue
        if args.team and not any(args.team.lower() in t.lower() for t in r["people"]["team"]):
            continue
        if args.social and args.social.lower() not in {s.lower() for s in r["socials"]}:
            continue

        snippet = None
        if rx:
            tf = tdir / (r["name"] + ".txt")
            if not tf.exists():
                continue
            body = tf.read_text(encoding="utf-8", errors="ignore")
            m = rx.search(body)
            if not m:
                continue
            a, b = max(0, m.start() - 50), m.end() + 80
            snippet = re.sub(r"\s+", " ", body[a:b]).strip()
        hits.append((r, snippet))

    hits = hits[: args.limit]
    if not hits:
        print("No matches.", file=sys.stderr)
        sys.exit(1)

    for r, snip in hits:
        year = (r.get("dates") or {}).get("likely_year") or "????"
        print(f"{GREEN}{r['name']}{RST} {DIM}({year}){RST}")
        if snip and rx:
            snip = rx.sub(lambda m: f"{ORANGE}{m.group(0)}{RST}", snip)
            print(f"  …{snip}…")
        if r["people"]["team"]:
            print(f"  {DIM}team:{RST} {', '.join(r['people']['team'][:4])}")
        if r["socials"]:
            print(f"  {DIM}socials:{RST} " +
                  ", ".join(f"{k}:{v[0]}" for k, v in r["socials"].items()))
    print(f"\n{len(hits)} result(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
