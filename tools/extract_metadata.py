#!/usr/bin/env python3
"""
extract_metadata.py — mine structured metadata from the whitepaper archive.

For every *.pdf in the repo root it runs `pdftotext`, caches the text, and
regex-extracts:
  - crypto wallet / contract addresses (ETH/EVM, BTC bech32, BTC legacy/P2SH)
  - social + community links (Twitter/X, Telegram, Discord, GitHub, ...)
  - release dates / years
  - founder & author name candidates

Outputs:
  data/whitepapers.json   full structured records
  data/whitepapers.csv    flat summary (one row per whitepaper)

No third-party deps. Needs `pdftotext` (poppler) on PATH.
"""
from __future__ import annotations
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache_txt"
DATA = ROOT / "data"

# ---- regex --------------------------------------------------------------
RE_ETH = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
RE_BTC_BECH32 = re.compile(r"\bbc1[ac-hj-np-z02-9]{11,71}\b")
RE_BTC_LEGACY = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")

SOCIAL_PATTERNS = {
    "twitter": re.compile(r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{2,30})", re.I),
    "telegram": re.compile(r"(?:https?://)?(?:www\.)?t\.me/([A-Za-z0-9_]{3,40})", re.I),
    "discord": re.compile(r"(?:https?://)?(?:www\.)?discord(?:\.gg|app\.com/invite)/([A-Za-z0-9]{4,20})", re.I),
    "github": re.compile(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]{1,40})", re.I),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([A-Za-z0-9_-]{2,60})", re.I),
    "reddit": re.compile(r"(?:https?://)?(?:www\.)?reddit\.com/r/([A-Za-z0-9_]{2,40})", re.I),
    "medium": re.compile(r"(?:https?://)?(?:www\.)?medium\.com/@?([A-Za-z0-9_.-]{2,40})", re.I),
    "facebook": re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9_.-]{2,60})", re.I),
}

# Full dates like "January 5, 2018" / "5 January 2018" / "2018-01-05"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
RE_DATE_FULL = re.compile(
    rf"\b(?:{MONTHS})\s+\d{{1,2}},?\s+(20[01]\d|202[0-6])\b"
    rf"|\b\d{{1,2}}\s+(?:{MONTHS})\s+(20[01]\d|202[0-6])\b"
    rf"|\b(20[01]\d|202[0-6])-\d{{2}}-\d{{2}}\b", re.I)
RE_YEAR = re.compile(r"\b(20[01]\d|202[0-6])\b")

ROLE_KEYWORDS = re.compile(
    r"\b(co-?founder|founder|ceo|cto|coo|cfo|cmo|cdo|chief\s+\w+\s+officer|"
    r"president|director|advisor|author)s?\b", re.I)
# A capitalized name: 2-4 capitalized tokens on ONE line (space-separated only,
# so it never bleeds across a \r\n into the next heading). Allows initials/accents.
RE_NAME = re.compile(
    r"\b([A-Z][a-zA-Zà-öø-ÿ'’.-]+(?:[ ]+[A-Z][a-zA-Zà-öø-ÿ'’.-]+){1,3})\b")

# Tokens that mark a phrase as a section heading / product label, not a person.
HEADING_TOKENS = {
    "white", "paper", "whitepaper", "token", "tokens", "coin", "protocol",
    "platform", "abstract", "contents", "content", "design", "security",
    "introduction", "overview", "summary", "executive", "chapter", "section",
    "roadmap", "team", "vision", "mission", "solution", "problem", "market",
    "technology", "network", "ecosystem", "framework", "model", "proof",
    "stake", "work", "smart", "contract", "contracts", "blockchain", "block",
    "chain", "table", "appendix", "figure", "reserved", "rights", "copyright",
    "introducing", "value", "proposition", "use", "case", "cases", "system",
    "what", "why", "how", "design", "services", "service", "decentralized",
    "distributed", "digital", "asset", "assets", "fund", "foundation", "ltd",
    "inc", "gmbh", "exchange", "wallet", "crypto", "currency", "finance",
    "financial", "global", "world", "the", "and", "for", "with", "our",
    "was", "co", "ity", "law", "client", "success", "today", "group",
    "marketing", "company", "limited", "corp", "official", "page",
    "senior", "vice", "development", "architect", "officer", "head",
    "manager", "lead", "engineer", "general", "partner", "operations",
    "relations", "community", "product", "project", "business", "junior",
}


def run_pdftotext(pdf: Path) -> str:
    cache_file = CACHE / (pdf.stem + ".txt")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="ignore")
    try:
        out = subprocess.run(
            ["pdftotext", "-q", str(pdf), "-"],
            capture_output=True, timeout=120,
        )
        text = out.stdout.decode("utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        text = ""
        print(f"  ! pdftotext failed for {pdf.name}: {e}", file=sys.stderr)
    cache_file.write_text(text, encoding="utf-8", errors="ignore")
    return text


def extract_socials(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, pat in SOCIAL_PATTERNS.items():
        handles = []
        for m in pat.finditer(text):
            h = m.group(1)
            # skip obvious doc/asset paths
            if name == "github" and h.lower() in {"www", "blog"}:
                continue
            if h.lower() in {"intent", "share", "home", "sharer", "hashtag"}:
                continue
            handles.append(h)
        if handles:
            # dedupe preserve order, cap 10
            seen, uniq = set(), []
            for h in handles:
                k = h.lower()
                if k not in seen:
                    seen.add(k); uniq.append(h)
            out[name] = uniq[:10]
    return out


def extract_dates(text: str) -> dict:
    full = []
    for m in RE_DATE_FULL.finditer(text):
        full.append(m.group(0).strip())
    years = [int(y) for y in RE_YEAR.findall(text)]
    year_counts = Counter(years)
    likely_year = None
    if year_counts:
        # heuristic: most frequent plausible publication year
        likely_year = year_counts.most_common(1)[0][0]
    return {
        "full_dates": list(dict.fromkeys(full))[:10],
        "likely_year": likely_year,
        "year_range": [min(years), max(years)] if years else None,
    }


def _looks_like_name(c: str) -> bool:
    toks = c.split()
    if not (2 <= len(toks) <= 4):
        return False
    if len(c) < 5:
        return False
    for t in toks:
        low = t.strip(".'’-").lower()
        if low in HEADING_TOKENS:
            return False
        if any(ch.isdigit() for ch in t):
            return False
        # all-caps word longer than 3 chars = acronym/heading, not a name part
        if t.isupper() and len(t) > 3:
            return False
    return True


def extract_names(text: str) -> dict:
    """Return {'team': [...role-confirmed...], 'authors': [...byline...]}.

    `team` names sit next to a role keyword (founder/CEO/...) — high precision.
    `authors` come from the title block — lower precision, useful as a fallback.
    """
    head = text[:2500]
    team, authors, seen = [], [], set()

    def add(bucket, name):
        name = name.strip(" .,-")
        # drop a trailing bare "Co" left over from a split "Co-founder"
        name = re.sub(r"\s+Co$", "", name)
        if not _looks_like_name(name):
            return
        k = name.lower()
        if k in seen:
            return
        seen.add(k)
        bucket.append(name)

    # role-confirmed names: the role keyword must sit IMMEDIATELY next to the
    # name (e.g. "Jane Doe, CEO" or "CTO: John Roe"), not just nearby.
    # role is matched case-insensitively (?i:...); the NAME stays case-SENSITIVE
    # so [A-Z] really means a capital letter (a global re.I would defeat that).
    role_nc = (
        r"(?i:co-?founder|founder|ceo|cto|coo|cfo|cmo|cdo|"
        r"chief\s+\w+\s+officer|president|director|advisor|author)s?")
    nm = (r"(?P<nm>[A-Z][a-zA-Zà-öø-ÿ'’.-]+"
          r"(?:[ ]+[A-Z][a-zA-Zà-öø-ÿ'’.-]+){1,3})")
    sep = r"[ ]*[,\-–—:]?[ ]*"
    adj_after = re.compile(rf"{nm}{sep}{role_nc}\b")
    adj_before = re.compile(rf"\b{role_nc}{sep}{nm}")
    for pat in (adj_after, adj_before):
        for m in pat.finditer(text):
            add(team, m.group("nm"))

    # byline / title-block names
    for m in RE_NAME.finditer(head):
        add(authors, m.group(1))

    return {"team": team[:12], "authors": authors[:12]}


def extract_wallets(text: str) -> dict[str, list[str]]:
    eth = list(dict.fromkeys(RE_ETH.findall(text)))[:20]
    bech = list(dict.fromkeys(RE_BTC_BECH32.findall(text)))[:20]
    legacy = list(dict.fromkeys(RE_BTC_LEGACY.findall(text)))
    # legacy base58 is noisy; keep only if it co-occurs with btc/bitcoin/donat words
    if legacy and not re.search(r"bitcoin|btc|donat|wallet|address", text, re.I):
        legacy = []
    legacy = legacy[:20]
    out = {}
    if eth:
        out["eth_evm"] = eth
    if bech:
        out["btc_bech32"] = bech
    if legacy:
        out["btc_legacy"] = legacy
    return out


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    pdfs = sorted((ROOT / "pdfs").glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs")

    records = []
    for i, pdf in enumerate(pdfs, 1):
        text = run_pdftotext(pdf)
        has_text = len(text.strip()) > 200
        rec = {
            "name": pdf.stem,
            "file": pdf.name,
            "size_bytes": pdf.stat().st_size,
            "has_text": has_text,
            "wallets": extract_wallets(text) if has_text else {},
            "socials": extract_socials(text) if has_text else {},
            "dates": extract_dates(text) if has_text else {},
            "people": extract_names(text) if has_text else {"team": [], "authors": []},
        }
        records.append(rec)
        if i % 50 == 0 or i == len(pdfs):
            print(f"  {i}/{len(pdfs)} processed")

    (DATA / "whitepapers.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    # flat CSV summary
    with (DATA / "whitepapers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "file", "likely_year", "wallets", "socials", "team", "authors", "has_text"])
        for r in records:
            wallets = sum(len(v) for v in r["wallets"].values())
            socials = "; ".join(f"{k}:{','.join(v)}" for k, v in r["socials"].items())
            team = "; ".join(r["people"]["team"][:6])
            authors = "; ".join(r["people"]["authors"][:6])
            w.writerow([
                r["name"], r["file"],
                (r["dates"] or {}).get("likely_year", ""),
                wallets, socials, team, authors, r["has_text"],
            ])

    # quick stats
    with_wallets = sum(1 for r in records if r["wallets"])
    with_socials = sum(1 for r in records if r["socials"])
    no_text = sum(1 for r in records if not r["has_text"])
    print(f"\nDone. {len(records)} records")
    print(f"  with wallets: {with_wallets}")
    print(f"  with socials: {with_socials}")
    print(f"  no extractable text (likely scanned): {no_text}")


if __name__ == "__main__":
    main()
