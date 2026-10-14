#!/usr/bin/env python3
"""federal-prize-feed: a machine-readable list of open U.S. federal prize competitions.

Challenge.gov was retired on March 30, 2026. Active federal challenges are now
published as web pages on USA.gov (https://www.usa.gov/find-active-challenge),
with no API or feed. This script reads those pages, adds challenges that
agencies post only on their own sites (agency_challenges.json, checked by
hand), and writes JSON, CSV, an Atom feed, an iCalendar file of deadlines and
a short Markdown digest. It also lists recent Federal Register notices about
prize competitions. Standard library only, Python 3.8+.

Made by MV2 of Munim, Inc. with AI agents. MIT license.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse
from xml.sax.saxutils import escape, quoteattr

__version__ = "0.3.0"

LISTING_URL = "https://www.usa.gov/find-active-challenge"
BASE = "https://www.usa.gov"
REPO_URL = "https://github.com/munimv2/federal-prize-feed"
ATOM_URL = "https://raw.githubusercontent.com/munimv2/federal-prize-feed/main/data/feed.xml"
USER_AGENT = "federal-prize-feed/%s (+%s)" % (__version__, REPO_URL)
CRAWL_DELAY = 10.0  # usa.gov/robots.txt asks for "Crawl-delay: 10"
AGENCY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agency_challenges.json")
SOURCE_USA = "usa.gov"
SOURCE_AGENCY = "agency page"

# Federal Register notices. Most prize notices cite 15 U.S.C. 3719, the
# America COMPETES prize authority, so "3719" finds them; the title filter
# drops the unrelated documents that also match.
FR_API = "https://www.federalregister.gov/api/v1/documents.json"
FR_TERMS = ("3719", "prize competition")
FR_FIELDS = ("document_number", "title", "publication_date", "agency_names", "html_url", "dates", "abstract")
FR_DAYS = 365
FR_TITLE_RE = re.compile(r"\b(challenges?|prizes?|competitions?|awards)\b", re.I)
FR_SKIP_RE = re.compile(
    r"information collection|generic clearance|millennium challenge|competitive impact"
    r"|public meeting|advisory committee|nominations", re.I)

# Fields compared between two refreshes for data/changes.json.
DIFF_FIELDS = ("title", "end_date", "end_time_et", "cash_prize_usd", "status")
CHANGELOG_KEEP = 200

# data/digest.md: "closing soon" window and how far back "new" reaches, in days.
DIGEST_DAYS = 30
DIGEST_NEW_DAYS = 7

# Labels in the "Key information" block of a USA.gov challenge page.
LABELS = {
    "sponsoring agency": "sponsor",
    "start date": "start_raw",
    "end date": "end_raw",
    "challenge type": "types",
    "prizes": "prizes",
    "contact": "contact",
}
STOP_PREFIXES = ("last updated", "share this page", "have a question")
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
    "main", "nav", "ol", "p", "section", "table", "td", "th", "tr", "ul",
}
SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "title"}
SHARE_HOSTS = ("facebook.com", "twitter.com", "x.com", "linkedin.com", "reddit.com", "pinterest.com")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
SLUG_RE = re.compile(r"^/challenges/([a-z0-9][a-z0-9-]*)/?$")
US_DATETIME_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?:\s*([AaPp])\.?[Mm]\.?)?)?")
LONG_DATE_RE = re.compile(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})")
MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion|[mk])?\b", re.I)

RECORD_KEYS = (
    "slug", "title", "url", "sponsor", "start_date", "start_time_et", "end_date",
    "end_time_et", "start_raw", "end_raw", "types", "prizes", "cash_prize_usd",
    "contact", "apply_url", "summary", "last_updated",
)
CSV_FIELDS = [
    "slug", "title", "sponsor", "status", "start_date", "end_date", "end_time_et",
    "cash_prize_usd", "types", "apply_url", "url", "contact", "last_updated", "source",
]


class _PageText(HTMLParser):
    """Flattens HTML into text lines (one per block element) and keeps links."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.lines = []
        self.links = []  # (line index, href, link text)
        self.h1 = None
        self._buf = []
        self._skip = 0
        self._in_h1 = False
        self._h1_buf = []
        self._href = None
        self._link_buf = []

    def _flush(self):
        text = " ".join("".join(self._buf).split())
        if text:
            self.lines.append(text)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
            return
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "h1" and self.h1 is None:
            self._in_h1 = True
            self._h1_buf = []
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._link_buf = []

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            if self._skip:
                self._skip -= 1
            return
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._link_buf).split())
            self.links.append((len(self.lines), self._href, text))
            self._href = None
        if tag == "h1" and self._in_h1:
            self.h1 = " ".join("".join(self._h1_buf).split()) or None
            self._in_h1 = False
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        self._buf.append(data)
        if self._in_h1:
            self._h1_buf.append(data)
        if self._href is not None:
            self._link_buf.append(data)

    def close(self):
        HTMLParser.close(self)
        self._flush()


def _page(html):
    page = _PageText()
    page.feed(html)
    page.close()
    return page


def parse_us_datetime(text):
    """'9/22/2026 9:00 AM ET' -> ('2026-09-22', '09:00'). Time may be None."""
    if not text:
        return None
    m = US_DATETIME_RE.search(text)
    if not m:
        return None
    try:
        date = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None
    clock = None
    if m.group(4):
        hour, minute = int(m.group(4)), int(m.group(5))
        ampm = (m.group(6) or "").lower()
        if ampm == "p" and hour < 12:
            hour += 12
        elif ampm == "a" and hour == 12:
            hour = 0
        if hour < 24 and minute < 60:
            clock = "%02d:%02d" % (hour, minute)
    return date.isoformat(), clock


def parse_long_date(text):
    """'August 13, 2026' -> '2026-08-13'. Falls back to the numeric form."""
    if not text:
        return None
    m = LONG_DATE_RE.search(text)
    if m and m.group(1)[:3].lower() in MONTHS:
        try:
            return dt.date(int(m.group(3)), MONTHS[m.group(1)[:3].lower()], int(m.group(2))).isoformat()
        except ValueError:
            pass
    parsed = parse_us_datetime(text)
    return parsed[0] if parsed else None


def _amount(line):
    m = MONEY_RE.search(line)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit in ("million", "m"):
        value *= 1000000
    elif unit == "billion":
        value *= 1000000000
    elif unit == "k":
        value *= 1000
    return int(round(value))


def cash_prize_usd(prize_lines):
    """The cash amount from a challenge's prize lines; None if there is none.

    A line that mentions cash wins; follow-on contracts and non-cash prizes
    are never counted as cash.
    """
    for line in prize_lines:
        low = line.lower()
        if "cash" in low and "non-cash" not in low:
            amount = _amount(line)
            if amount is not None:
                return amount
    for line in prize_lines:
        low = line.lower()
        if "contract" in low or "non-cash" in low or "sbir" in low:
            continue
        amount = _amount(line)
        if amount is not None:
            return amount
    return None


def parse_listing(html, base=BASE):
    """URLs of the challenge pages linked from the USA.gov listing, in page order."""
    seen, urls = set(), []
    for _, href, _ in _page(html).links:
        full = urljoin(base + "/", href.strip())
        parsed = urlparse(full)
        if parsed.netloc not in ("www.usa.gov", "usa.gov"):
            continue
        m = SLUG_RE.match(parsed.path)
        if not m:
            continue
        url = "https://www.usa.gov/challenges/" + m.group(1)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _label_of(line):
    key = line.strip().rstrip(":").strip().lower()
    if key in LABELS:
        return key, ""
    low = line.lower()
    for label in LABELS:
        if low.startswith(label + ":"):
            return label, line[len(label) + 1:].strip()
    return None, None


def _is_stop(line):
    return line.lower().startswith(STOP_PREFIXES)


def _external(href):
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.netloc.lower()
    if host == "usa.gov" or host.endswith(".usa.gov"):
        return False
    return not any(host == h or host.endswith("." + h) for h in SHARE_HOSTS)


def parse_detail(html, url=""):
    """One USA.gov challenge page -> a record dict."""
    page = _page(html)
    lines = page.lines

    title_idx = 0
    if page.h1 and page.h1 in lines:
        title_idx = lines.index(page.h1)
    start = title_idx
    for i in range(title_idx, len(lines)):
        if lines[i].lower().rstrip(":") == "key information":
            start = i + 1
            break
    end = len(lines)
    for i in range(title_idx, len(lines)):
        if lines[i].lower().startswith(("share this page", "have a question")):
            end = i
            break

    fields, current = {}, None
    for i in range(start, end):
        line = lines[i]
        if _is_stop(line):
            break
        label, rest = _label_of(line)
        if label is not None:
            current = LABELS[label] if LABELS[label] not in fields else None
            if current is not None:
                fields[current] = [rest] if rest else []
            continue
        if current is not None:
            fields[current].append(line)

    last_updated = None
    for i, line in enumerate(lines):
        if line.lower().startswith("last updated"):
            rest = line.split(":", 1)[1].strip() if ":" in line else ""
            if not rest and i + 1 < len(lines):
                rest = lines[i + 1]
            last_updated = parse_long_date(rest)
            break

    apply_url = None
    for idx, href, _ in page.links:
        if title_idx <= idx <= end and _external(href.strip()):
            apply_url = href.strip()
            break

    summary = None
    for i in range(title_idx + 1, end):
        line = lines[i]
        if len(line) >= 60 and _label_of(line)[0] is None and not _is_stop(line):
            summary = line
            break

    def first(key):
        values = fields.get(key) or []
        return values[0] if values else None

    start_raw, end_raw = first("start_raw"), first("end_raw")
    opens, closes = parse_us_datetime(start_raw), parse_us_datetime(end_raw)
    prizes = fields.get("prizes", [])
    contacts = fields.get("contact", [])
    contact = next((c for c in contacts if "@" in c), contacts[0] if contacts else None)
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] if url else None
    return {
        "slug": slug,
        "title": page.h1,
        "url": url,
        "sponsor": first("sponsor"),
        "start_date": opens[0] if opens else None,
        "start_time_et": opens[1] if opens else None,
        "end_date": closes[0] if closes else None,
        "end_time_et": closes[1] if closes else None,
        "start_raw": start_raw,
        "end_raw": end_raw,
        "types": fields.get("types", []),
        "prizes": prizes,
        "cash_prize_usd": cash_prize_usd(prizes),
        "contact": contact,
        "apply_url": apply_url,
        "summary": summary,
        "last_updated": last_updated,
        "source": SOURCE_USA,
    }


def status(record, today=None):
    """'open', 'upcoming' or 'closed' on the given ISO date (default: today)."""
    today = today or dt.date.today().isoformat()
    opens, closes = record.get("start_date"), record.get("end_date")
    if closes and closes < today:
        return "closed"
    if opens and opens > today:
        return "upcoming"
    return "open"


def fetch(url, timeout=30, accept="text/html"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, "replace")


def fetch_json(url, timeout=30):
    return json.loads(fetch(url, timeout, accept="application/json"))


def collect(listing_url=LISTING_URL, delay=CRAWL_DELAY, fetcher=fetch, log=None):
    """Read the listing and every challenge page it links to."""
    records = []
    for url in parse_listing(fetcher(listing_url)):
        if delay:
            time.sleep(delay)
        try:
            record = parse_detail(fetcher(url), url)
        except Exception as exc:  # one bad page must not sink the run
            if log:
                log("skip %s: %s" % (url, exc))
            continue
        if not record["sponsor"] and not record["end_date"]:
            continue  # linked page is not a challenge
        records.append(record)
    return records


def load_agency(path=AGENCY_FILE, today=None):
    """Challenges from agency_challenges.json that have not closed yet."""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    records = []
    for item in data.get("challenges", []):
        record = {key: item.get(key) for key in RECORD_KEYS}
        record["types"] = item.get("types") or []
        record["prizes"] = item.get("prizes") or []
        record["cash_prize_usd"] = cash_prize_usd(record["prizes"])
        record["last_updated"] = item.get("checked") or data.get("checked")
        record["source"] = SOURCE_AGENCY
        if status(record, today) != "closed":
            records.append(record)
    return records


def _norm_url(url):
    return (url or "").strip().rstrip("/").lower()


def merge(primary, extra):
    """primary plus the extra records that are not already in it (same slug or application link)."""
    slugs = {r.get("slug") for r in primary}
    links = {_norm_url(r.get("apply_url")) for r in primary if r.get("apply_url")}
    out = list(primary)
    for record in extra:
        if record.get("slug") in slugs:
            continue
        if record.get("apply_url") and _norm_url(record["apply_url"]) in links:
            continue
        out.append(record)
    return out


def federal_register_url(term, since):
    params = [
        ("conditions[term]", term),
        ("conditions[type][]", "NOTICE"),
        ("conditions[publication_date][gte]", since),
        ("order", "newest"),
        ("per_page", "100"),
    ]
    params += [("fields[]", field) for field in FR_FIELDS]
    return FR_API + "?" + urlencode(params)


def is_prize_notice(title):
    return bool(title) and bool(FR_TITLE_RE.search(title)) and not FR_SKIP_RE.search(title)


def parse_federal_register(payload):
    """Prize and challenge notices from one Federal Register API response."""
    notices = []
    for doc in payload.get("results") or []:
        title = " ".join((doc.get("title") or "").split())
        if not is_prize_notice(title):
            continue
        agencies = []
        for name in doc.get("agency_names") or []:
            if name and name not in agencies:
                agencies.append(name)
        notices.append({
            "document_number": doc.get("document_number"),
            "title": title,
            "agencies": agencies,
            "publication_date": doc.get("publication_date"),
            "url": doc.get("html_url"),
            "dates": doc.get("dates"),
            "abstract": doc.get("abstract"),
        })
    return notices


def collect_federal_register(since=None, fetcher=fetch_json, terms=FR_TERMS, today=None):
    """Prize notices published since the given ISO date (default: the last FR_DAYS days), newest first."""
    if since is None:
        day = dt.date.fromisoformat(today) if today else dt.date.today()
        since = (day - dt.timedelta(days=FR_DAYS)).isoformat()
    found = {}
    for term in terms:
        for notice in parse_federal_register(fetcher(federal_register_url(term, since))):
            found.setdefault(notice["document_number"], notice)
    notices = sorted(found.values(), key=lambda n: (n.get("document_number") or ""), reverse=True)
    notices.sort(key=lambda n: (n.get("publication_date") or ""), reverse=True)
    return notices, since


def to_notices_document(notices, since, generated_at=None):
    return {
        "source": FR_API,
        "generated_at": generated_at
        or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terms": list(FR_TERMS),
        "since": since,
        "count": len(notices),
        "note": "Federal Register notices whose titles name a challenge, prize or competition. "
                "Many announce challenges that USA.gov does not list; some are closed.",
        "notices": notices,
    }


def to_document(records, today=None, generated_at=None):
    today = today or dt.date.today().isoformat()
    out = []
    for record in records:
        record = dict(record)
        record["status"] = status(record, today)
        out.append(record)
    out.sort(key=lambda r: (r.get("end_date") or "9999-12-31", r.get("title") or ""))
    return {
        "source": LISTING_URL,
        "generated_at": generated_at
        or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(out),
        "note": "USA.gov lists select active federal challenges. Records with source 'agency page' "
                "are challenges agencies post only on their own sites, checked by hand (agency_challenges.json).",
        "challenges": out,
    }


def _brief(record):
    return {key: record.get(key) for key in ("slug", "title", "sponsor", "end_date", "cash_prize_usd", "url")}


def diff_documents(old, new):
    """Challenges added, removed and changed between two active.json documents."""
    old_by = {r.get("slug"): r for r in (old or {}).get("challenges", [])}
    new_by = {r.get("slug"): r for r in new.get("challenges", [])}
    added = [_brief(r) for slug, r in new_by.items() if slug not in old_by]
    removed = [_brief(r) for slug, r in old_by.items() if slug not in new_by]
    changed = []
    for slug, record in new_by.items():
        before = old_by.get(slug)
        if before is None:
            continue
        for field in DIFF_FIELDS:
            if before.get(field) != record.get(field):
                changed.append({"slug": slug, "field": field, "old": before.get(field), "new": record.get(field)})
    return {"added": added, "removed": removed, "changed": changed}


def add_to_changelog(entries, change, date, keep=CHANGELOG_KEEP):
    """Newest-first change log; a refresh that changed nothing adds no entry."""
    if not (change["added"] or change["removed"] or change["changed"]):
        return list(entries)
    entry = {"date": date}
    entry.update(change)
    return ([entry] + list(entries))[:keep]


def to_csv_rows(document):
    rows = []
    for record in document["challenges"]:
        row = {}
        for field in CSV_FIELDS:
            value = record.get(field)
            if isinstance(value, list):
                value = "; ".join(value)
            row[field] = "" if value is None else value
        rows.append(row)
    return rows


def _ics_escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,") \
        .replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line):
    """RFC 5545 line folding: at most 75 octets per line."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, chunk, size, limit = [], "", 0, 75
    for ch in line:
        width = len(ch.encode("utf-8"))
        if size + width > limit:
            parts.append(chunk)
            chunk, size, limit = "", 0, 74  # continuation lines start with a space
        chunk += ch
        size += width
    parts.append(chunk)
    return "\r\n ".join(parts)


def to_ics(document):
    """An all-day calendar event on each challenge's closing date."""
    stamp = document["generated_at"].replace("-", "").replace(":", "")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Munim Inc//federal-prize-feed %s//EN" % __version__,
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Federal prize competition deadlines",
    ]
    for record in document["challenges"]:
        closes = record.get("end_date")
        if not closes:
            continue
        day = dt.date.fromisoformat(closes)
        summary = "Closes: %s" % (record.get("title") or record.get("slug"))
        if record.get("cash_prize_usd"):
            summary += " ($%s)" % format(record["cash_prize_usd"], ",")
        desc = "Sponsor: %s\nCloses: %s\nApply: %s\nListing: %s" % (
            record.get("sponsor") or "", record.get("end_raw") or closes,
            record.get("apply_url") or "", record.get("url") or "")
        lines += [
            "BEGIN:VEVENT",
            _fold("UID:%s-closes@federal-prize-feed.munimv2" % record.get("slug")),
            "DTSTAMP:%s" % stamp,
            "DTSTART;VALUE=DATE:%s" % day.strftime("%Y%m%d"),
            "DTEND;VALUE=DATE:%s" % (day + dt.timedelta(days=1)).strftime("%Y%m%d"),
            _fold("SUMMARY:" + _ics_escape(summary)),
            _fold("DESCRIPTION:" + _ics_escape(desc)),
        ]
        if record.get("url"):
            lines.append(_fold("URL:" + record["url"]))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def to_atom(document, feed_url=ATOM_URL):
    """An Atom feed with one entry per challenge, most recently updated first."""
    generated = document["generated_at"]

    def updated(record):
        return "%sT00:00:00Z" % record["last_updated"] if record.get("last_updated") else generated

    records = sorted(document["challenges"], key=lambda r: r.get("slug") or "")
    records.sort(key=updated, reverse=True)
    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "  <title>Open U.S. federal prize competitions</title>",
        "  <subtitle>Federal challenges listed on USA.gov and agency pages, by federal-prize-feed</subtitle>",
        "  <id>%s</id>" % escape(feed_url),
        "  <link rel=\"self\" href=%s/>" % quoteattr(feed_url),
        "  <link rel=\"alternate\" href=%s/>" % quoteattr(REPO_URL),
        "  <updated>%s</updated>" % generated,
        "  <author><name>MV2 of Munim, Inc.</name></author>",
        "  <generator uri=%s version=%s>federal-prize-feed</generator>" % (
            quoteattr(REPO_URL), quoteattr(__version__)),
    ]
    for record in records:
        title = record.get("title") or record.get("slug") or ""
        if record.get("cash_prize_usd"):
            title += " ($%s)" % format(record["cash_prize_usd"], ",")
        closes = record.get("end_date") or "not stated"
        if record.get("end_date") and record.get("end_time_et"):
            closes += " %s ET" % record["end_time_et"]
        parts = [
            "Sponsor: %s" % (record.get("sponsor") or "not stated"),
            "Closes: %s" % closes,
            "Status: %s" % (record.get("status") or status(record)),
        ]
        if record.get("summary"):
            parts.append(record["summary"])
        if record.get("apply_url"):
            parts.append("Apply: %s" % record["apply_url"])
        entry_id = record.get("url") or "urn:federal-prize-feed:%s" % record.get("slug")
        out += [
            "  <entry>",
            "    <title>%s</title>" % escape(title),
            "    <id>%s</id>" % escape(entry_id),
        ]
        if record.get("url"):
            out.append("    <link rel=\"alternate\" href=%s/>" % quoteattr(record["url"]))
        out += [
            "    <updated>%s</updated>" % updated(record),
            "    <summary>%s</summary>" % escape("\n".join(parts)),
            "  </entry>",
        ]
    out.append("</feed>")
    return "\n".join(out) + "\n"


def _usd_total(amount):
    if amount >= 1000000:
        return "$%.1f million" % (amount / 1000000.0)
    return "$" + format(amount, ",")


def _md_text(text):
    return (text or "").replace("[", "\\[").replace("]", "\\]")


def _digest_line(record, today):
    title = _md_text(record.get("title") or record.get("slug"))
    if record.get("url"):
        title = "[%s](%s)" % (title, record["url"])
    closes = record.get("end_date") or "no closing date"
    if record.get("end_date") and record.get("end_time_et"):
        closes += " %s ET" % record["end_time_et"]
    cash = record.get("cash_prize_usd")
    parts = [
        "**%s**" % closes,
        title,
        record.get("sponsor") or "sponsor not stated",
        "$%s" % format(cash, ",") if cash else "no cash prize stated",
    ]
    if status(record, today) == "upcoming" and record.get("start_date"):
        parts.append("opens %s" % record["start_date"])
    return "- " + " · ".join(parts)


def to_digest(document, changelog=None, today=None, days=DIGEST_DAYS, new_days=DIGEST_NEW_DAYS):
    """A Markdown summary: what is new, what closes soon, what opens later, and the rest."""
    today = today or document["generated_at"][:10]
    day = dt.date.fromisoformat(today)
    soon = (day + dt.timedelta(days=days)).isoformat()
    since = (day - dt.timedelta(days=new_days)).isoformat()
    live = [r for r in document["challenges"] if status(r, today) != "closed"]
    by_slug = {r.get("slug"): r for r in live}

    new, seen = [], set()
    for entry in changelog or []:
        if (entry.get("date") or "") < since:
            continue
        for item in entry.get("added") or []:
            slug = item.get("slug")
            if slug in by_slug and slug not in seen:
                seen.add(slug)
                new.append(by_slug[slug])
    closing = [r for r in live if r.get("end_date") and r["end_date"] <= soon]
    taken = {r.get("slug") for r in closing}
    upcoming = [r for r in live if r.get("slug") not in taken and status(r, today) == "upcoming"]
    taken.update(r.get("slug") for r in upcoming)
    later = [r for r in live if r.get("slug") not in taken]

    total = sum(r.get("cash_prize_usd") or 0 for r in live)
    out = [
        "# Open U.S. federal prize competitions",
        "",
        "Built %s by [federal-prize-feed](%s) from USA.gov, agency pages and the Federal Register. "
        "%d open or upcoming challenges, about %s in stated cash prizes."
        % (today, REPO_URL, len(live), _usd_total(total)),
        "",
    ]
    for heading, records in (
        ("New in the last %d days" % new_days, new),
        ("Closing in the next %d days" % days, closing),
        ("Opening later", upcoming),
        ("Open, closing later", later),
    ):
        if records:
            out += ["## " + heading, ""] + [_digest_line(r, today) for r in records] + [""]
    out.append("Dates are copied from the official pages; phase and registration deadlines can be earlier. "
               "Read the official rules before you apply. Not an official government product.")
    return "\n".join(out) + "\n"


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _read_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_outputs(document, out_dir, notices=None, changelog=None):
    os.makedirs(out_dir, exist_ok=True)
    _write_json(os.path.join(out_dir, "active.json"), document)
    with open(os.path.join(out_dir, "active.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(to_csv_rows(document))
    with open(os.path.join(out_dir, "deadlines.ics"), "w", encoding="utf-8", newline="") as f:
        f.write(to_ics(document))
    with open(os.path.join(out_dir, "feed.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(to_atom(document))
    with open(os.path.join(out_dir, "digest.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(to_digest(document, changelog))
    if notices is not None:
        _write_json(os.path.join(out_dir, "federal-register.json"), notices)
    if changelog is not None:
        _write_json(os.path.join(out_dir, "changes.json"), {
            "note": "Challenges added, removed or changed at each refresh, newest first.",
            "entries": changelog,
        })


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Open U.S. federal prize competitions as JSON, CSV, Atom, iCalendar and a Markdown digest.")
    ap.add_argument("--out", default="data", help="output folder (default: data)")
    ap.add_argument("--from-json", metavar="FILE", help="rebuild outputs from an earlier active.json, no network")
    ap.add_argument("--delay", type=float, default=CRAWL_DELAY,
                    help="seconds between page requests (default: 10, per usa.gov robots.txt)")
    ap.add_argument("--agency", default=AGENCY_FILE,
                    help="hand-checked agency challenges to merge in (default: agency_challenges.json; '' to skip)")
    ap.add_argument("--no-federal-register", action="store_true",
                    help="do not fetch Federal Register prize notices")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    log = lambda msg: print(msg, file=sys.stderr)  # noqa: E731
    previous = _read_json(os.path.join(args.out, "active.json"))
    notices, changelog = None, None
    if args.from_json:
        old = _read_json(args.from_json)
        document = to_document(old["challenges"], generated_at=old.get("generated_at"))
    else:
        records = collect(delay=args.delay, log=log)
        if not records:
            log("no challenges found; the USA.gov layout may have changed. Nothing written.")
            return 1
        document = to_document(merge(records, load_agency(args.agency)))
        if not args.no_federal_register:
            try:
                found, since = collect_federal_register()
                notices = to_notices_document(found, since, document["generated_at"])
            except Exception as exc:  # keep the previous file rather than fail the refresh
                log("federal register skipped: %s" % exc)
        if previous:
            log_doc = _read_json(os.path.join(args.out, "changes.json")) or {}
            changelog = add_to_changelog(log_doc.get("entries", []), diff_documents(previous, document),
                                         document["generated_at"][:10])
    write_outputs(document, args.out, notices=notices, changelog=changelog)
    print("%d challenges -> %s" % (document["count"], args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
