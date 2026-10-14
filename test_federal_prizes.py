import datetime as dt
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import federal_prizes as fp  # noqa: E402

DETAIL = """<!DOCTYPE html><html><head><title>xTech|Search 10 | USAGov</title>
<script>var label = "Contact";</script></head>
<body>
<nav><ul><li><a href="/contact">Contact</a></li></ul></nav>
<main id="main-content">
<h1 id="skip-to-h1">xTech|Search 10</h1>
<p>The U.S. Army is seeking innovative technology solutions from eligible small businesses around the U.S.</p>
<div class="usa-summary-box"><p><strong>Key information</strong></p>
<div><h3>Sponsoring agency</h3><p>U.S. Army xTech </p></div>
<div><h3>Start date</h3><p>09/10/2026 5:00 PM ET  </p></div>
<div><h3>End date</h3><p>10/19/2026 5:00 PM ET</p></div>
<div><h3>Challenge type</h3><ul><li>Ideation</li><li>Software and application development</li></ul></div>
<div><h3>Prizes</h3><ul><li>Cash prize:&nbsp; $1,000,000</li>
<li>Follow-on contract opportunities: Up to $12,700,000</li></ul></div>
<div><h3>Contact</h3><p><a href="mailto:xtech@army.mil">xtech@army.mil</a></p></div>
</div>
<p><a href="https://xtech.army.mil/competition/xtechsearch10/">Apply for xTech|Search 10</a></p>
<p>LAST UPDATED: August 13, 2026</p>
<p>SHARE THIS PAGE: <a href="https://www.facebook.com/sharer/sharer.php?u=x">Facebook</a></p>
<h2>Have a question?</h2>
</main></body></html>
"""

DETAIL_DL = """<html><body>
<h1>One CDC Data Platform (1CDP) Innovation Challenge</h1>
<dl><dt>Sponsoring agency:</dt><dd>Centers for Disease Control</dd>
<dt>Start date</dt><dd>10/28/2026 8:00 AM ET</dd>
<dt>End date</dt><dd>10/28/2026 6:00 PM ET</dd>
<dt>Prizes</dt><dd>Non-cash prizes: A discovery session with 1CDP staff</dd>
<dt>Contact</dt><dd>1CDP@cdc.gov</dd></dl>
<p><a href="https://www.cdc.gov/one-cdc-data-platform.html">Apply for the 1CDP Innovation Challenge</a></p>
<p><span>LAST UPDATED:</span></p><p>August 5, 2026</p>
</body></html>
"""

LISTING = """<html><body><main>
<a href="/challenges/xtech-search-10">xTech|Search 10</a>
<a href="https://www.usa.gov/challenges/darpa-surgical-competition/">DARPA Surgical Competition</a>
<a href="/challenges/xtech-search-10">again</a>
<a href="/challenge-how-to-participate">How to participate</a>
<a href="https://example.com/challenges/other">elsewhere</a>
<a href="/challenges/foo/bar">nested</a>
</main></body></html>
"""

NOT_A_CHALLENGE = "<html><body><h1>About challenges</h1><p>Nothing to see.</p></body></html>"

AGENCY = {
    "checked": "2026-10-14",
    "challenges": [
        {"slug": "lunar", "title": "Lunar Grounding", "url": "https://www.nasa.gov/lunar/",
         "sponsor": "NASA", "start_date": "2026-10-05", "end_date": "2027-01-15",
         "prizes": ["Up to $150,000 in prizes"], "apply_url": "https://work.crowdplat.com/challenge/lunar"},
        {"slug": "old", "title": "Old one", "url": "https://www.nasa.gov/old/",
         "sponsor": "NASA", "end_date": "2026-01-01", "prizes": []},
        {"slug": "dup-link", "title": "Same as xTech", "url": "https://example.gov/x",
         "sponsor": "Army", "end_date": "2026-12-01",
         "apply_url": "https://XTECH.army.mil/competition/xtechsearch10"},
    ],
}

FR_PAYLOAD = {
    "count": 5,
    "results": [
        {"document_number": "2026-12440", "title": "Public Notice: Design Challenge for National Memorial",
         "publication_date": "2026-06-22",
         "agency_names": ["Transportation Department", "Federal Highway Administration"],
         "html_url": "https://www.federalregister.gov/documents/2026/06/22/2026-12440/x",
         "dates": "Submissions must be received on or before October 20, 2026.", "abstract": "A."},
        {"document_number": "2026-07846", "title": "Solicitation of Proposals for  Impact Awards",
         "publication_date": "2026-04-22",
         "agency_names": ["Transportation Department", "Transportation Department"],
         "html_url": "https://www.federalregister.gov/documents/2026/04/22/2026-07846/y",
         "dates": None, "abstract": None},
        {"document_number": "2026-20704",
         "title": "Millennium Challenge Corporation Selection Criteria and Methodology Report",
         "publication_date": "2026-10-09", "agency_names": ["Millennium Challenge Corporation"]},
        {"document_number": "2026-20720", "title": "Challenges and Solutions in Food Traceability; Public Meeting",
         "publication_date": "2026-10-09", "agency_names": ["Food and Drug Administration"]},
        {"document_number": "2026-20432", "title": "Biweekly Notice; Applications and Amendments to Licenses",
         "publication_date": "2026-10-06", "agency_names": ["Nuclear Regulatory Commission"]},
    ],
}


class ParseDetailTest(unittest.TestCase):
    def setUp(self):
        self.rec = fp.parse_detail(DETAIL, "https://www.usa.gov/challenges/xtech-search-10")

    def test_fields(self):
        r = self.rec
        self.assertEqual(r["slug"], "xtech-search-10")
        self.assertEqual(r["title"], "xTech|Search 10")
        self.assertEqual(r["sponsor"], "U.S. Army xTech")
        self.assertEqual((r["start_date"], r["start_time_et"]), ("2026-09-10", "17:00"))
        self.assertEqual((r["end_date"], r["end_time_et"]), ("2026-10-19", "17:00"))
        self.assertEqual(r["types"], ["Ideation", "Software and application development"])
        self.assertEqual(r["cash_prize_usd"], 1000000)
        self.assertEqual(r["contact"], "xtech@army.mil")
        self.assertEqual(r["apply_url"], "https://xtech.army.mil/competition/xtechsearch10/")
        self.assertEqual(r["last_updated"], "2026-08-13")
        self.assertEqual(r["source"], "usa.gov")
        self.assertTrue(r["summary"].startswith("The U.S. Army is seeking"))

    def test_nav_label_before_title_is_ignored(self):
        self.assertNotEqual(self.rec["contact"], None)
        self.assertNotIn("Contact", self.rec["contact"])

    def test_definition_list_layout(self):
        r = fp.parse_detail(DETAIL_DL, "https://www.usa.gov/challenges/1cdp-innovation-challenge/")
        self.assertEqual(r["slug"], "1cdp-innovation-challenge")
        self.assertEqual(r["sponsor"], "Centers for Disease Control")
        self.assertEqual(r["end_date"], "2026-10-28")
        self.assertEqual(r["end_time_et"], "18:00")
        self.assertIsNone(r["cash_prize_usd"])
        self.assertEqual(r["contact"], "1CDP@cdc.gov")
        self.assertEqual(r["apply_url"], "https://www.cdc.gov/one-cdc-data-platform.html")
        self.assertEqual(r["last_updated"], "2026-08-05")
        self.assertEqual(fp.status(r, "2026-10-13"), "upcoming")

    def test_inline_label(self):
        html = "<h1>T</h1><p>Start date: 9/8/2026 9:30 AM ET</p><p>End date: 10/14/2026 12:00 PM ET</p>"
        r = fp.parse_detail(html, "https://www.usa.gov/challenges/t")
        self.assertEqual((r["start_date"], r["start_time_et"]), ("2026-09-08", "09:30"))
        self.assertEqual((r["end_date"], r["end_time_et"]), ("2026-10-14", "12:00"))


class ParseListingTest(unittest.TestCase):
    def test_links(self):
        self.assertEqual(fp.parse_listing(LISTING), [
            "https://www.usa.gov/challenges/xtech-search-10",
            "https://www.usa.gov/challenges/darpa-surgical-competition",
        ])


class ValuesTest(unittest.TestCase):
    def test_us_datetime(self):
        self.assertEqual(fp.parse_us_datetime("3/04/2027 11:59 PM ET"), ("2027-03-04", "23:59"))
        self.assertEqual(fp.parse_us_datetime("09/25/2025 11:59 ET (Phase 1)"), ("2025-09-25", "11:59"))
        self.assertEqual(fp.parse_us_datetime("1/2/2027 12:30 AM ET"), ("2027-01-02", "00:30"))
        self.assertEqual(fp.parse_us_datetime("1/2/2027 12:30 PM ET"), ("2027-01-02", "12:30"))
        self.assertEqual(fp.parse_us_datetime("10/14/2026"), ("2026-10-14", None))
        self.assertIsNone(fp.parse_us_datetime("13/40/2026 1:00 PM"))
        self.assertIsNone(fp.parse_us_datetime(None))

    def test_long_date(self):
        self.assertEqual(fp.parse_long_date("September 3, 2026"), "2026-09-03")
        self.assertEqual(fp.parse_long_date("Sept. 3, 2026"), "2026-09-03")
        self.assertEqual(fp.parse_long_date("9/3/2026"), "2026-09-03")
        self.assertIsNone(fp.parse_long_date("soon"))

    def test_cash(self):
        self.assertEqual(fp.cash_prize_usd(
            ["Total cash prizes: up to $550,000, split among 3 phases and multiple solvers"]), 550000)
        self.assertEqual(fp.cash_prize_usd(
            ["Follow-on contract opportunities: Up to $12,700,000", "Cash prize:  $1,500,000"]), 1500000)
        self.assertEqual(fp.cash_prize_usd(["Up to $5 million in awards"]), 5000000)
        self.assertEqual(fp.cash_prize_usd(["Phase 1: $5K each"]), 5000)
        self.assertEqual(fp.cash_prize_usd(
            ["Up to $2 million in total prizes: up to four winners, each up to $500,000",
             "Non-cash prize: a no-cost flight test"]), 2000000)
        self.assertIsNone(fp.cash_prize_usd(["Non-cash prize: plaque"]))
        self.assertIsNone(fp.cash_prize_usd([]))

    def test_status(self):
        rec = {"start_date": "2026-09-10", "end_date": "2026-10-19"}
        self.assertEqual(fp.status(rec, "2026-10-13"), "open")
        self.assertEqual(fp.status(rec, "2026-10-19"), "open")
        self.assertEqual(fp.status(rec, "2026-10-20"), "closed")
        self.assertEqual(fp.status(rec, "2026-09-01"), "upcoming")
        self.assertEqual(fp.status({}, "2026-10-13"), "open")


class OutputTest(unittest.TestCase):
    def setUp(self):
        rec = fp.parse_detail(DETAIL, "https://www.usa.gov/challenges/xtech-search-10")
        self.doc = fp.to_document([rec], today="2026-10-13", generated_at="2026-10-13T22:40:00Z")

    def test_document(self):
        self.assertEqual(self.doc["count"], 1)
        self.assertEqual(self.doc["challenges"][0]["status"], "open")

    def test_ics(self):
        ics = fp.to_ics(self.doc)
        for line in ics.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line)
        flat = ics.replace("\r\n ", "")
        self.assertTrue(flat.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(flat.endswith("END:VCALENDAR\r\n"))
        self.assertIn("DTSTART;VALUE=DATE:20261019", flat)
        self.assertIn("DTEND;VALUE=DATE:20261020", flat)
        self.assertIn("DTSTAMP:20261013T224000Z", flat)
        self.assertIn("SUMMARY:Closes: xTech|Search 10 ($1\\,000\\,000)", flat)
        self.assertIn("\\nApply: https://xtech.army.mil/competition/xtechsearch10/", flat)

    def test_fold_multibyte(self):
        line = "DESCRIPTION:" + "é" * 100
        folded = fp._fold(line)
        for part in folded.split("\r\n"):
            self.assertLessEqual(len(part.encode("utf-8")), 75)
        self.assertEqual(folded.replace("\r\n ", ""), line)

    def test_csv_rows(self):
        row = fp.to_csv_rows(self.doc)[0]
        self.assertEqual(row["types"], "Ideation; Software and application development")
        self.assertEqual(row["cash_prize_usd"], 1000000)
        self.assertEqual(row["source"], "usa.gov")

    def test_atom(self):
        extra = {"slug": "a&b", "title": "Fish & <Chips>", "end_date": "2026-12-01", "status": "open"}
        doc = fp.to_document([self.doc["challenges"][0], extra], today="2026-10-13",
                             generated_at="2026-10-13T22:40:00Z")
        atom = fp.to_atom(doc)
        root = ET.fromstring(atom.encode("utf-8"))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        self.assertEqual(root.tag, "{http://www.w3.org/2005/Atom}feed")
        self.assertEqual(root.find("a:updated", ns).text, "2026-10-13T22:40:00Z")
        entries = root.findall("a:entry", ns)
        self.assertEqual(len(entries), 2)
        # the entry without last_updated takes the feed time, so it sorts first
        self.assertEqual(entries[0].find("a:title", ns).text, "Fish & <Chips>")
        self.assertEqual(entries[0].find("a:id", ns).text, "urn:federal-prize-feed:a&b")
        self.assertIsNone(entries[0].find("a:link", ns))
        self.assertEqual(entries[1].find("a:title", ns).text, "xTech|Search 10 ($1,000,000)")
        self.assertEqual(entries[1].find("a:updated", ns).text, "2026-08-13T00:00:00Z")
        self.assertEqual(entries[1].find("a:link", ns).get("href"),
                         "https://www.usa.gov/challenges/xtech-search-10")
        summary = entries[1].find("a:summary", ns).text
        self.assertIn("Closes: 2026-10-19 17:00 ET", summary)
        self.assertIn("Apply: https://xtech.army.mil/competition/xtechsearch10/", summary)

    def test_write_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp.write_outputs(self.doc, tmp)
            for name in ("active.json", "active.csv", "deadlines.ics", "feed.xml"):
                self.assertTrue(os.path.exists(os.path.join(tmp, name)), name)
            for name in ("federal-register.json", "changes.json"):
                self.assertFalse(os.path.exists(os.path.join(tmp, name)), name)
            with open(os.path.join(tmp, "active.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["count"], 1)

    def test_write_optional_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            notices = fp.to_notices_document([], "2025-10-14", "2026-10-14T00:00:00Z")
            fp.write_outputs(self.doc, tmp, notices=notices, changelog=[])
            with open(os.path.join(tmp, "federal-register.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["since"], "2025-10-14")
            with open(os.path.join(tmp, "changes.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["entries"], [])


class CollectTest(unittest.TestCase):
    def test_collect_skips_non_challenge_pages(self):
        pages = {
            fp.LISTING_URL: LISTING,
            "https://www.usa.gov/challenges/xtech-search-10": DETAIL,
            "https://www.usa.gov/challenges/darpa-surgical-competition": NOT_A_CHALLENGE,
        }
        records = fp.collect(delay=0, fetcher=lambda url: pages[url])
        self.assertEqual([r["slug"] for r in records], ["xtech-search-10"])

    def test_collect_survives_a_failing_page(self):
        def fetcher(url):
            if url == fp.LISTING_URL:
                return LISTING
            if url.endswith("darpa-surgical-competition"):
                raise IOError("boom")
            return DETAIL
        logged = []
        records = fp.collect(delay=0, fetcher=fetcher, log=logged.append)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(logged), 1)


class AgencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "agency.json")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(AGENCY, f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_drops_closed(self):
        records = fp.load_agency(self.path, today="2026-10-14")
        self.assertEqual([r["slug"] for r in records], ["lunar", "dup-link"])
        lunar = records[0]
        self.assertEqual(lunar["source"], "agency page")
        self.assertEqual(lunar["cash_prize_usd"], 150000)
        self.assertEqual(lunar["last_updated"], "2026-10-14")
        self.assertEqual(lunar["types"], [])
        self.assertIsNone(lunar["end_time_et"])

    def test_missing_file(self):
        self.assertEqual(fp.load_agency(os.path.join(self.tmp.name, "nope.json")), [])
        self.assertEqual(fp.load_agency(""), [])

    def test_merge_skips_duplicates(self):
        usa = fp.parse_detail(DETAIL, "https://www.usa.gov/challenges/xtech-search-10")
        same_slug = {"slug": "xtech-search-10", "title": "copy"}
        merged = fp.merge([usa], fp.load_agency(self.path, today="2026-10-14") + [same_slug])
        self.assertEqual([r["slug"] for r in merged], ["xtech-search-10", "lunar"])
        self.assertEqual(merged[0]["title"], "xTech|Search 10")


class FederalRegisterTest(unittest.TestCase):
    def test_url(self):
        url = fp.federal_register_url("3719", "2025-10-14")
        query = parse_qs(urlparse(url).query)
        self.assertTrue(url.startswith(fp.FR_API + "?"))
        self.assertEqual(query["conditions[term]"], ["3719"])
        self.assertEqual(query["conditions[type][]"], ["NOTICE"])
        self.assertEqual(query["conditions[publication_date][gte]"], ["2025-10-14"])
        self.assertEqual(query["fields[]"], list(fp.FR_FIELDS))

    def test_title_filter(self):
        self.assertTrue(fp.is_prize_notice("Announcement of Requirements and Registration for EHIgnite Challenge"))
        self.assertTrue(fp.is_prize_notice("Centennial Challenges Deep Space Food Challenge: Mars to Table Registration"))
        self.assertFalse(fp.is_prize_notice("Agency Information Collection Activities: Challenge and Prize Competition"))
        self.assertFalse(fp.is_prize_notice("Combined Notice of Filings #1"))
        self.assertFalse(fp.is_prize_notice(""))

    def test_parse(self):
        notices = fp.parse_federal_register(FR_PAYLOAD)
        self.assertEqual([n["document_number"] for n in notices], ["2026-12440", "2026-07846"])
        self.assertEqual(notices[0]["agencies"], ["Transportation Department", "Federal Highway Administration"])
        self.assertEqual(notices[1]["agencies"], ["Transportation Department"])
        self.assertEqual(notices[1]["title"], "Solicitation of Proposals for Impact Awards")
        self.assertEqual(notices[0]["dates"], "Submissions must be received on or before October 20, 2026.")
        self.assertEqual(fp.parse_federal_register({"count": 0}), [])

    def test_collect_dedupes_and_sorts(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return FR_PAYLOAD
        notices, since = fp.collect_federal_register(fetcher=fetcher, today="2026-10-14")
        self.assertEqual(since, "2025-10-14")
        self.assertEqual(len(calls), len(fp.FR_TERMS))
        self.assertEqual([n["document_number"] for n in notices], ["2026-12440", "2026-07846"])


class ChangesTest(unittest.TestCase):
    def test_diff(self):
        old = {"challenges": [
            {"slug": "a", "title": "A", "end_date": "2026-11-01", "status": "open"},
            {"slug": "b", "title": "B", "end_date": "2026-10-01", "status": "open"},
        ]}
        new = {"challenges": [
            {"slug": "a", "title": "A", "end_date": "2026-12-01", "status": "open"},
            {"slug": "c", "title": "C", "end_date": "2027-01-01", "status": "upcoming", "cash_prize_usd": 5000},
        ]}
        change = fp.diff_documents(old, new)
        self.assertEqual([r["slug"] for r in change["added"]], ["c"])
        self.assertEqual(change["added"][0]["cash_prize_usd"], 5000)
        self.assertEqual([r["slug"] for r in change["removed"]], ["b"])
        self.assertEqual(change["changed"], [
            {"slug": "a", "field": "end_date", "old": "2026-11-01", "new": "2026-12-01"}])

    def test_changelog(self):
        empty = {"added": [], "removed": [], "changed": []}
        self.assertEqual(fp.add_to_changelog([{"date": "x"}], empty, "2026-10-14"), [{"date": "x"}])
        change = {"added": [{"slug": "c"}], "removed": [], "changed": []}
        log = fp.add_to_changelog([{"date": "2026-10-13"}], change, "2026-10-14", keep=2)
        self.assertEqual([e["date"] for e in log], ["2026-10-14", "2026-10-13"])
        log = fp.add_to_changelog(log, change, "2026-10-15", keep=2)
        self.assertEqual([e["date"] for e in log], ["2026-10-15", "2026-10-14"])


class MainTest(unittest.TestCase):
    def test_from_json_rebuild(self):
        rec = fp.parse_detail(DETAIL, "https://www.usa.gov/challenges/xtech-search-10")
        doc = fp.to_document([rec], today="2026-10-13", generated_at="2026-10-13T22:40:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            out = os.path.join(tmp, "out")
            self.assertEqual(fp.main(["--from-json", src, "--out", out]), 0)
            for name in ("active.json", "active.csv", "deadlines.ics", "feed.xml"):
                self.assertTrue(os.path.exists(os.path.join(out, name)), name)


SNAPSHOT = os.path.join(HERE, "data", "active.json")
AGENCY_FILE = os.path.join(HERE, "agency_challenges.json")
NOTICES = os.path.join(HERE, "data", "federal-register.json")
FEED = os.path.join(HERE, "data", "feed.xml")


@unittest.skipUnless(os.path.exists(SNAPSHOT), "no data/active.json snapshot")
class SnapshotTest(unittest.TestCase):
    def setUp(self):
        with open(SNAPSHOT, encoding="utf-8") as f:
            self.doc = json.load(f)

    def test_shape(self):
        items = self.doc["challenges"]
        self.assertEqual(self.doc["count"], len(items))
        self.assertGreater(len(items), 0)
        ends = []
        for r in items:
            for key in ("slug", "title", "url", "sponsor", "end_date", "status", "source"):
                self.assertTrue(r.get(key), (r.get("slug"), key))
            self.assertIn(r["source"], ("usa.gov", "agency page"), r["slug"])
            if r["source"] == "usa.gov":
                self.assertTrue(r["url"].startswith("https://www.usa.gov/challenges/"), r["slug"])
                self.assertTrue(r["url"].endswith("/" + r["slug"]), r["slug"])
            else:
                self.assertTrue(r["url"].startswith("https://"), r["slug"])
            dt.date.fromisoformat(r["end_date"])
            if r.get("start_date"):
                dt.date.fromisoformat(r["start_date"])
                self.assertLessEqual(r["start_date"], r["end_date"], r["slug"])
            self.assertIn(r["status"], ("open", "upcoming", "closed"))
            if r.get("prizes"):
                self.assertEqual(fp.cash_prize_usd(r["prizes"]), r.get("cash_prize_usd"), r["slug"])
            if r.get("end_raw"):
                self.assertEqual(fp.parse_us_datetime(r["end_raw"])[0], r["end_date"], r["slug"])
            ends.append(r["end_date"])
        self.assertEqual(ends, sorted(ends))
        self.assertEqual(len({r["slug"] for r in items}), len(items))

    def test_renders(self):
        fp.to_ics(self.doc)
        fp.to_csv_rows(self.doc)
        ET.fromstring(fp.to_atom(self.doc).encode("utf-8"))


@unittest.skipUnless(os.path.exists(AGENCY_FILE), "no agency_challenges.json")
class AgencyFileTest(unittest.TestCase):
    def test_entries(self):
        with open(AGENCY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        dt.date.fromisoformat(data["checked"])
        slugs = set()
        for item in data["challenges"]:
            for key in ("slug", "title", "url", "sponsor", "end_date", "checked"):
                self.assertTrue(item.get(key), (item.get("slug"), key))
            self.assertNotIn(item["slug"], slugs)
            slugs.add(item["slug"])
            self.assertTrue(item["url"].startswith("https://"), item["slug"])
            dt.date.fromisoformat(item["end_date"])
            dt.date.fromisoformat(item["checked"])
            if item.get("start_date"):
                self.assertLessEqual(item["start_date"], item["end_date"], item["slug"])


@unittest.skipUnless(os.path.exists(NOTICES), "no data/federal-register.json")
class NoticesFileTest(unittest.TestCase):
    def test_shape(self):
        with open(NOTICES, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["count"], len(doc["notices"]))
        dates = [n["publication_date"] for n in doc["notices"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        for n in doc["notices"]:
            self.assertTrue(fp.is_prize_notice(n["title"]), n["title"])
            self.assertTrue(n["url"].startswith("https://www.federalregister.gov/documents/"), n["url"])


@unittest.skipUnless(os.path.exists(FEED), "no data/feed.xml")
class FeedFileTest(unittest.TestCase):
    def test_parses(self):
        with open(FEED, "rb") as f:
            root = ET.fromstring(f.read())
        self.assertEqual(root.tag, "{http://www.w3.org/2005/Atom}feed")
        self.assertGreater(len(root.findall("{http://www.w3.org/2005/Atom}entry")), 0)


if __name__ == "__main__":
    unittest.main()
