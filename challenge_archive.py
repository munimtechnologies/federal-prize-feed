#!/usr/bin/env python3
"""challenge_archive: an open dataset of every challenge in the Challenge.gov archive.

Challenge.gov was retired on March 30, 2026. Its listings survive only as one
Markdown file per challenge in GSA's read-only GitHub repository
(https://github.com/GSA/challenges-and-prizes, folder _archive/root/_all-challenges),
with no CSV, JSON or API. This script downloads those files at a pinned commit,
reads their front matter and writes one clean record per challenge (JSON and
CSV) plus a summary of challenges and cash prizes offered by year, department,
type and legal authority. Names and emails of challenge managers are left out
on purpose. Standard library only, Python 3.8+.

Made by MV2 of Munim, Inc. with AI agents. Apache-2.0 license.
"""

import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

__version__ = "0.4.0"

REPO_URL = "https://github.com/munimtechnologies/federal-prize-feed"
USER_AGENT = "federal-prize-feed-archive/%s (+%s)" % (__version__, REPO_URL)
GSA_REPO = "GSA/challenges-and-prizes"
GSA_API = "https://api.github.com/repos/" + GSA_REPO
GSA_RAW = "https://raw.githubusercontent.com/" + GSA_REPO
GSA_BLOB = "https://github.com/" + GSA_REPO + "/blob"
ARCHIVE_DIR = "_archive/root/_all-challenges"
FILE_DELAY = 0.1  # seconds between raw file downloads

# Front matter keys that name or email a person. They are never copied out.
PERSONAL_KEYS = ("challenge-manager", "challenge-manager-email", "point-of-contact")

# Challenge.gov's own challenge types. One of them contains commas, so the
# field is matched against this list instead of being split on ", ".
KNOWN_TYPES = (
    "Ideas",
    "Technology demonstration and hardware",
    "Software and apps",
    "Creative (multimedia & design)",
    "Scientific",
    "Analytics, visualizations, algorithms",
    "Business plans",
    "Nominations",
)
COMPETES = "America COMPETES Act (15 U.S.C. 3719)"
COMPETES_RE = re.compile(r"\bcompetes\b|3719", re.I)

TOP_DEPARTMENTS = 25
LARGEST = 15
# Georgetown CSET counted 607 federal prize competitions on Challenge.gov for
# 2020-2025 ("Prize Competitions and the Genesis Mission"); used as a cross-check.
CSET_YEARS = (2020, 2025)
CSET_COUNT = 607

KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_-]*):(?:[ \t]+(.*))?[ \t]*$")
BLOCK_RE = re.compile(r"^[|>][+-]?$")
TAG_RE = re.compile(r"<[^>]+>")
LIQUID_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)(?:\s*(million|billion|thousand|[mbk])\b)?", re.I)
BARE_NUMBER_RE = re.compile(r"^\$?\s*(\d[\d,]*(?:\.\d+)?)\s*$")
MULTIPLIERS = {"thousand": 1000, "k": 1000, "million": 10 ** 6, "m": 10 ** 6,
               "billion": 10 ** 9, "b": 10 ** 9}
US_DATE_RE = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp])\.?[Mm]\.?)?")
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")
FY_RE = re.compile(r"^(?:FY\s*'?)?(\d{4}|\d{2})$", re.I)

CSV_FIELDS = ("id", "title", "department", "sub_agency", "status", "types", "cash_usd",
              "cash_source", "prize", "start", "end", "end_year", "fiscal_year", "authority",
              "legal_authority", "external_url", "archive_url")


# ---------------------------------------------------------------- front matter

def split_front_matter(text):
    """Return (front matter lines, body lines). Tolerates a doubled opening ---."""
    lines = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].rstrip() != "---":
        return [], lines
    while i + 1 < len(lines) and lines[i + 1].rstrip() == "---":
        i += 1
    for j in range(i + 1, len(lines)):
        if lines[j].rstrip() == "---":
            return lines[i + 1:j], lines[j + 1:]
    return lines[i + 1:], []


def _fold(lines):
    """Join lines the way YAML folds them: one break is a space, a blank line a newline."""
    out, para = [], []
    for line in lines:
        if line.strip():
            para.append(line.strip())
        elif para:
            out.append(" ".join(para))
            para = []
    if para:
        out.append(" ".join(para))
    return "\n".join(out)


def _scalar(value):
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    low = value.lower()
    if low in ("", "null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    return value


def parse_front_matter(lines):
    """Read the simple YAML the archive uses: top-level keys, plain or quoted
    scalars over one or more lines, and | or > block scalars. Not a full YAML parser."""
    entries, key, first, rest = [], None, None, []
    for line in lines:
        if line.startswith("#"):
            continue
        m = KEY_RE.match(line)
        if m:
            if key is not None:
                entries.append((key, first, rest))
            key, first, rest = m.group(1), (m.group(2) or "").strip(), []
        elif key is not None:
            rest.append(line)
    if key is not None:
        entries.append((key, first, rest))
    data = {}
    for key, first, rest in entries:
        if BLOCK_RE.match(first):
            if first[0] == "|":
                indent = min((len(l) - len(l.lstrip()) for l in rest if l.strip()), default=0)
                value = "\n".join(l[indent:] for l in rest).strip("\n")
            else:
                value = _fold(rest)
            data[key] = value or None
        else:
            data[key] = _scalar(_fold([first] + rest))
    return data


# ---------------------------------------------------------------- fields

def clean_text(value):
    """Plain text: no HTML tags, Liquid tags or entities, single spaces."""
    if value is None:
        return None
    text = LIQUID_RE.sub("", str(value))
    text = html.unescape(TAG_RE.sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _amount(number, unit):
    try:
        value = Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None
    if unit:
        value *= MULTIPLIERS[unit.lower()]
    return int(value)


def money_mentions(text):
    """Every dollar amount in text, as whole dollars ("$1.2 million" -> 1200000)."""
    if not text:
        return []
    found = (_amount(m.group(1), m.group(2)) for m in MONEY_RE.finditer(str(text)))
    return [a for a in found if a is not None]


def parse_cash(value):
    """The total-prize-offered-cash field as whole dollars, or None if not stated."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    m = BARE_NUMBER_RE.match(text)
    if m:
        return _amount(m.group(1), None)
    found = money_mentions(text)
    return max(found) if found else None


def parse_when(value):
    """'05/16/2019 04:59 PM' -> '2019-05-16T16:59'; a date alone -> '2019-05-16'."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    m = US_DATE_RE.match(text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = minute = None
        if m.group(4):
            hour, minute = int(m.group(4)) % 12, int(m.group(5))
            if m.group(6).lower() == "p":
                hour += 12
    else:
        m = ISO_DATE_RE.match(text)
        if not m:
            return None
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4)) if m.group(4) else None
        minute = int(m.group(5)) if m.group(5) else None
    try:
        when = dt.datetime(year, month, day, hour or 0, minute or 0)
    except ValueError:
        return None
    return when.strftime("%Y-%m-%dT%H:%M") if hour is not None else when.strftime("%Y-%m-%d")


def fiscal_year(iso):
    """U.S. federal fiscal year of an ISO date (FY2020 runs Oct 2019 - Sep 2020)."""
    if not iso:
        return None
    year, month = int(iso[:4]), int(iso[5:7])
    return year + 1 if month >= 10 else year


def parse_fy(value):
    if value is None or isinstance(value, bool):
        return None
    m = FY_RE.match(str(value).strip())
    if not m:
        return None
    n = int(m.group(1))
    return n + 2000 if n < 100 else n


def challenge_types(value):
    text = clean_text(value)
    if not text:
        return []
    low = text.lower()
    return [t for t in KNOWN_TYPES if t.lower() in low] or [text]


def authority_bucket(value):
    text = clean_text(value)
    if not text:
        return "not stated"
    return COMPETES if COMPETES_RE.search(text) else "other authority"


def split_agency(value):
    """'Department of Labor - Veterans' Employment ...' -> (department, sub-agency)."""
    text = clean_text(value)
    if not text:
        return None, None
    dept, _, sub = text.partition(" - ")
    return dept.strip() or None, sub.strip() or None


def make_record(data, path, ref):
    cid = str(data.get("challenge-id") or "").strip()
    cash_field = parse_cash(data.get("total-prize-offered-cash"))
    tagline = clean_text(data.get("tagline"))
    cash_tagline = max(money_mentions(tagline), default=None)
    if cash_field is not None:
        cash, source = cash_field, "field"
    elif cash_tagline is not None:
        cash, source = cash_tagline, "tagline"
    else:
        cash, source = None, None
    start = parse_when(data.get("submission-start"))
    end = parse_when(data.get("submission-end"))
    dept, sub = split_agency(data.get("agency"))
    prize = data.get("prize")
    fy_reported = parse_fy(data.get("fiscal-year"))
    permalink = clean_text(data.get("permalink")) or ""
    return {
        "id": int(cid) if cid.isdigit() else None,
        "title": clean_text(data.get("challenge-title")),
        "status": clean_text(data.get("status")),
        "agency": clean_text(data.get("agency")),
        "department": dept,
        "sub_agency": sub,
        "partners_federal": clean_text(data.get("partner-agencies-federal")),
        "partners_non_federal": clean_text(data.get("partners-non-federal")),
        "types": challenge_types(data.get("type-of-challenge")),
        "cash_usd": cash,
        "cash_source": source,
        "cash_usd_field": cash_field,
        "prize": prize if isinstance(prize, bool) else None,
        "start": start,
        "end": end,
        "end_year": int(end[:4]) if end else None,
        "fiscal_year": fy_reported or fiscal_year(end),
        "fiscal_year_reported": fy_reported,
        "legal_authority": clean_text(data.get("legal-authority")),
        "authority": authority_bucket(data.get("legal-authority")),
        "tagline": tagline[:500] if tagline else None,
        "external_url": clean_text(data.get("external-url")),
        "challenge_gov_url": "https://www.challenge.gov" + permalink if permalink.startswith("/") else None,
        "archive_url": "%s/%s/%s" % (GSA_BLOB, ref, urllib.parse.quote(path)),
        "file": path.rsplit("/", 1)[-1],
    }


def build_records(files, ref):
    """files: (path, text) pairs. Returns (records, duplicate files, unparsed files)."""
    records, seen, duplicates, unparsed = [], set(), [], []
    for path, text in sorted(files):
        data = parse_front_matter(split_front_matter(text)[0])
        if not data:
            unparsed.append(path.rsplit("/", 1)[-1])
            continue
        rec = make_record(data, path, ref)
        key = rec["id"] if rec["id"] is not None else rec["file"]
        if key in seen:
            duplicates.append(rec["file"])
            continue
        seen.add(key)
        records.append(rec)
    records.sort(key=lambda r: (r["id"] is None, r["id"] or 0, r["file"]))
    return records, duplicates, unparsed


# ---------------------------------------------------------------- summary

def _days(start, end):
    try:
        return (dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start)).days
    except ValueError:
        return None


def summarize(records, duplicates=(), unparsed=(), source=None):
    years = defaultdict(lambda: {"challenges": 0, "cash_usd": 0, "tagline_usd": 0, "cash_missing": 0})
    depts = defaultdict(lambda: {"challenges": 0, "cash_usd": 0})
    types, authority, status = Counter(), Counter(), Counter()
    windows = []
    for r in records:
        year = r["end_year"] or (int(r["start"][:4]) if r["start"] else 0)
        row, dep = years[year], depts[r["department"] or "not stated"]
        row["challenges"] += 1
        dep["challenges"] += 1
        if r["cash_usd"] is None:
            row["cash_missing"] += 1
        else:
            row["cash_usd"] += r["cash_usd"]
            dep["cash_usd"] += r["cash_usd"]
            if r["cash_source"] == "tagline":
                row["tagline_usd"] += r["cash_usd"]
        types.update(r["types"] or ["not stated"])
        authority[r["authority"]] += 1
        status[r["status"] or "not stated"] += 1
        if r["start"] and r["end"]:
            days = _days(r["start"], r["end"])
            if days is not None and days >= 0:
                windows.append(days)
    with_cash = [r for r in records if r["cash_usd"] is not None]
    largest = sorted(with_cash, key=lambda r: (-r["cash_usd"], r["id"] or 0))[:LARGEST]
    by_dept = sorted(depts.items(), key=lambda kv: (-kv[1]["challenges"], kv[0]))
    lo, hi = CSET_YEARS
    return {
        "source": source or {},
        "challenges": len(records),
        "duplicate_files": list(duplicates),
        "unparsed_files": list(unparsed),
        "cash_usd_total": sum(r["cash_usd"] for r in with_cash),
        "cash_usd_field_total": sum(r["cash_usd_field"] or 0 for r in records),
        "cash_from_tagline": sum(1 for r in records if r["cash_source"] == "tagline"),
        "cash_missing": len(records) - len(with_cash),
        "non_prize": sum(1 for r in records if r["prize"] is False),
        "status": dict(status.most_common()),
        "window_days_median": statistics.median(windows) if windows else None,
        "by_year": [dict(year=y or "unknown", **years[y])
                    for y in sorted(years, key=lambda y: (y == 0, y))],
        "by_department": [dict(department=d, **v) for d, v in by_dept[:TOP_DEPARTMENTS]],
        "departments": len(depts),
        "by_type": dict(types.most_common()),
        "by_authority": dict(authority.most_common()),
        "largest": [{k: r[k] for k in ("id", "title", "department", "end_year", "cash_usd", "cash_source")}
                    for r in largest],
        "cset_check": {"years": "%d-%d" % (lo, hi), "cset_count": CSET_COUNT,
                       "challenges": sum(1 for r in records if r["end_year"] and lo <= r["end_year"] <= hi)},
    }


def fmt_usd(n):
    return "{:,}".format(n)


def summary_markdown(s):
    src = s["source"]
    out = [
        "# The Challenge.gov archive in numbers",
        "",
        "Built by `challenge_archive.py` from %s at commit `%s` (folder `%s`, %s files)."
        % (src.get("repo", GSA_REPO), str(src.get("commit", ""))[:12], src.get("folder", ARCHIVE_DIR),
           src.get("files", "?")),
        "",
        "- Challenges (unique IDs): %d, from %d departments or independent agencies"
        % (s["challenges"], s["departments"]),
        "- Cash prizes offered: $%s (cash field: $%s; read from the tagline when the field was empty: %d challenges)"
        % (fmt_usd(s["cash_usd_total"]), fmt_usd(s["cash_usd_field_total"]), s["cash_from_tagline"]),
        "- No cash amount stated: %d; marked as not a prize: %d" % (s["cash_missing"], s["non_prize"]),
        "- Median submission window: %s days" % (s["window_days_median"],),
        "- Duplicate files skipped: %d; files without front matter: %d"
        % (len(s["duplicate_files"]), len(s["unparsed_files"])),
        "",
        "## By the year the submission window closed",
        "",
        "| Year | Challenges | Cash prizes (USD) | Of which read from the tagline | No amount stated |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in s["by_year"]:
        out.append("| %s | %d | %s | %s | %d |" % (row["year"], row["challenges"], fmt_usd(row["cash_usd"]),
                                                 fmt_usd(row["tagline_usd"]), row["cash_missing"]))
    out += ["", "## Largest cash prizes", "", "| ID | Challenge | Department | Closed | Cash (USD) |",
            "|---:|---|---|---:|---:|"]
    for r in s["largest"]:
        out.append("| %s | %s | %s | %s | %s%s |" % (r["id"], r["title"], r["department"], r["end_year"],
                                                     fmt_usd(r["cash_usd"]),
                                                     " (tagline)" if r["cash_source"] == "tagline" else ""))
    out += ["", "## Departments (top %d by number of challenges)" % TOP_DEPARTMENTS, "",
            "| Department | Challenges | Cash prizes (USD) |", "|---|---:|---:|"]
    for d in s["by_department"]:
        out.append("| %s | %d | %s |" % (d["department"], d["challenges"], fmt_usd(d["cash_usd"])))
    out += ["", "## Challenge types (a challenge can have several)", "", "| Type | Challenges |", "|---|---:|"]
    out += ["| %s | %d |" % kv for kv in s["by_type"].items()]
    out += ["", "## Legal authority", "", "| Authority | Challenges |", "|---|---:|"]
    out += ["| %s | %d |" % kv for kv in s["by_authority"].items()]
    c = s["cset_check"]
    out += [
        "", "## Cross-check",
        "",
        "Georgetown CSET counted %d federal prize competitions on Challenge.gov for %s. This archive has %d "
        "challenges whose submission window closed in those years. The two counts use different date rules, "
        "so they are not expected to match exactly." % (c["cset_count"], c["years"], c["challenges"]),
        "",
        "## Limits",
        "",
        "- The archive holds only what agencies posted on Challenge.gov. Some federal prizes were never listed there.",
        "- Cash is the amount offered, as the agency wrote it, not what was paid out. When the cash field is empty, "
        "the largest dollar amount in the tagline is used and marked `tagline`.",
        "- Years follow the submission end date (or the start date when there is no end date).",
        "- Names and emails of challenge managers are not copied.",
        "",
        "Made by MV2 of Munim, Inc. with AI agents. Code Apache-2.0; this summary and the data CC BY 4.0. "
        "Source records are U.S. government works published by GSA.",
        "",
    ]
    return "\n".join(out)


def write_outputs(records, summary, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "archive.json"), "w", encoding="utf-8") as f:
        json.dump({"source": summary["source"], "count": len(records), "challenges": records},
                  f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "archive.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for r in records:
            w.writerow(["; ".join(r[k]) if k == "types" else ("" if r[k] is None else r[k])
                        for k in CSV_FIELDS])
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_markdown(summary))


# ---------------------------------------------------------------- download

def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url):
    return json.loads(fetch(url).decode("utf-8"))


def resolve_commit(ref, get_json=fetch_json):
    """(commit sha, root tree sha) of a branch, tag or sha of the GSA repository."""
    data = get_json("%s/commits/%s" % (GSA_API, ref))
    return data["sha"], data["commit"]["tree"]["sha"]


def list_archive(tree_sha, get_json=fetch_json):
    """Paths of the archive's .md files, walking one folder level per request."""
    tree = get_json("%s/git/trees/%s" % (GSA_API, tree_sha))
    for name in ARCHIVE_DIR.split("/"):
        sub = [t for t in tree.get("tree", []) if t.get("path") == name and t.get("type") == "tree"]
        if not sub:
            raise RuntimeError("folder %s not found in %s" % (name, GSA_REPO))
        tree = get_json("%s/git/trees/%s" % (GSA_API, sub[0]["sha"]))
    if tree.get("truncated"):
        raise RuntimeError("GitHub truncated the archive folder listing")
    return sorted("%s/%s" % (ARCHIVE_DIR, t["path"]) for t in tree.get("tree", [])
                  if t.get("type") == "blob" and t.get("path", "").endswith(".md"))


def download(paths, sha, cache_dir=None, delay=FILE_DELAY, getter=fetch, log=print):
    """Fetch each file at the pinned commit, reusing cache_dir/<sha>/ when present."""
    files, failed = [], []
    for n, path in enumerate(paths, 1):
        name = path.rsplit("/", 1)[-1]
        cached = os.path.join(cache_dir, sha, name) if cache_dir else None
        if cached and os.path.exists(cached):
            with open(cached, "rb") as f:
                body = f.read()
        else:
            try:
                body = getter("%s/%s/%s" % (GSA_RAW, sha, urllib.parse.quote(path)))
            except (OSError, ValueError) as err:
                failed.append("%s (%s)" % (name, err))
                continue
            if cached:
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                with open(cached, "wb") as f:
                    f.write(body)
            time.sleep(delay)
        files.append((path, body.decode("utf-8", errors="replace")))
        if n % 200 == 0:
            log("[%s] %d/%d files" % (time.strftime("%H:%M:%S"), n, len(paths)))
    return files, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build an open dataset from the Challenge.gov archive.")
    ap.add_argument("--out", default=os.path.join("data", "archive"))
    ap.add_argument("--cache", help="keep downloaded files here, per commit")
    ap.add_argument("--ref", default="staging", help="branch, tag or commit of %s" % GSA_REPO)
    ap.add_argument("--src", help="read .md files from this local folder instead of downloading")
    ap.add_argument("--delay", type=float, default=FILE_DELAY)
    args = ap.parse_args(argv)
    if args.src:
        files = []
        for name in sorted(n for n in os.listdir(args.src) if n.endswith(".md")):
            with open(os.path.join(args.src, name), encoding="utf-8", errors="replace") as f:
                files.append(("%s/%s" % (ARCHIVE_DIR, name), f.read()))
        sha, failed = args.ref, []
    else:
        sha, tree_sha = resolve_commit(args.ref)
        paths = list_archive(tree_sha)
        print("%s at %s: %d files in %s" % (GSA_REPO, sha, len(paths), ARCHIVE_DIR))
        files, failed = download(paths, sha, args.cache, args.delay)
    records, duplicates, unparsed = build_records(files, sha)
    source = {"repo": "https://github.com/" + GSA_REPO, "ref": args.ref, "commit": sha,
              "folder": ARCHIVE_DIR, "files": len(files) + len(failed), "failed": failed}
    summary = summarize(records, duplicates, unparsed, source)
    write_outputs(records, summary, args.out)
    print("%d challenges, $%s in cash prizes offered; %d failed downloads, %d duplicates, %d unparsed"
          % (summary["challenges"], fmt_usd(summary["cash_usd_total"]), len(failed),
             len(duplicates), len(unparsed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
