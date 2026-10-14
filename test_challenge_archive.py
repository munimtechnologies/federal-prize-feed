# Tests for challenge_archive.py. Made by MV2 of Munim, Inc. with AI agents. Apache-2.0 license.
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import challenge_archive as ca

PATH_A = ca.ARCHIVE_DIR + "/1012-magquest.md"
PATH_B = ca.ARCHIVE_DIR + "/1085-veterans-employment-challenge.md"

MAGQUEST = "\n".join([
    "---",
    "layout: front-matter-data",
    "permalink: /challenge/magquest/",
    "challenge-id: 1012",
    "status: closed",
    "sidenav: false",
    "challenge-title: MagQuest",
    "tagline: A $1.2 million challenge to advance how we measure Earth's magnetic field.",
    "agency: Department of Defense - National Geospatial-Intelligence Agency",
    "partner-agencies-federal: ",
    "partners-non-federal: ",
    "external-url: https://www.magquest.com/",
    "total-prize-offered-cash: ",
    "type-of-challenge: Scientific",
    "submission-start: 03/21/2019 09:00 AM",
    "submission-end: 05/16/2019 04:59 PM",
    "submission-link:  ",
    "prize: true",
    "---",
    "",
])

VETERANS = "\n".join([
    "---",
    "---",
    "challenge-title: Veterans' Employment Challenge",
    "layout: front-matter-data",
    "permalink: /challenge/veterans-employment-challenge/",
    "challenge-id: 1085",
    "status: closed",
    "tagline: Help veterans find",
    "  good jobs, faster.",
    "agency: Department of Labor - Veterans' Employment and Training Service",
    "partner-agencies-federal: Department of Veterans Affairs, Department of Defense",
    "partners-non-federal: null",
    "external-url: null",
    "total-prize-offered-cash: $1,000,000",
    "type-of-challenge: Software and apps, Analytics, visualizations, algorithms",
    "submission-start: 12/11/2019 10:30 AM",
    "submission-end: 01/24/2020 5:00 PM",
    "fiscal-year: FY20",
    "legal-authority: America COMPETES Act",
    "challenge-manager: Jane Doe",
    "challenge-manager-email: jane.doe@example.gov",
    "point-of-contact: jane.doe@example.gov",
    "description: <p>Phase I: ideas.",
    "  Rules: see <a href=\"{{ site.baseurl }}/rules\">below</a>.</p>",
    "prizes: >-",
    "  <p>Phase I: $100,000</p>",
    "",
    "  <p>Phase II: $200,000</p>",
    "prize: true",
    "---",
    "<!-- Description start -->",
    "### Description",
    "<p>Body text</p>",
])

NO_DATES = "\n".join([
    "---",
    "challenge-id: 7",
    "challenge-title: No dates",
    "total-prize-offered-cash: TBD",
    "prize: false",
    "---",
])


def fm(text):
    return ca.parse_front_matter(ca.split_front_matter(text)[0])


class FrontMatterTest(unittest.TestCase):
    def test_doubled_opening_delimiter(self):
        lines, body = ca.split_front_matter(VETERANS)
        self.assertEqual(lines[0], "challenge-title: Veterans' Employment Challenge")
        self.assertEqual(body[0], "<!-- Description start -->")

    def test_no_front_matter(self):
        self.assertEqual(ca.split_front_matter("just text\n")[0], [])

    def test_plain_values_and_nulls(self):
        d = fm(MAGQUEST)
        self.assertEqual(d["challenge-id"], "1012")
        self.assertIs(d["prize"], True)
        self.assertIs(d["sidenav"], False)
        self.assertIsNone(d["partner-agencies-federal"])
        self.assertIsNone(d["submission-link"])
        self.assertEqual(d["external-url"], "https://www.magquest.com/")

    def test_multiline_and_block_scalars(self):
        d = fm(VETERANS)
        self.assertEqual(d["tagline"], "Help veterans find good jobs, faster.")
        self.assertEqual(d["description"],
                         "<p>Phase I: ideas. Rules: see <a href=\"{{ site.baseurl }}/rules\">below</a>.</p>")
        self.assertEqual(d["prizes"], "<p>Phase I: $100,000</p>\n<p>Phase II: $200,000</p>")
        self.assertIsNone(d["partners-non-federal"])
        self.assertIs(d["prize"], True)

    def test_literal_block_and_quotes(self):
        d = ca.parse_front_matter(["a: |", "  one", "    two", "b: 'it''s'", 'c: "say \\"hi\\""', "# note"])
        self.assertEqual(d["a"], "one\n  two")
        self.assertEqual(d["b"], "it's")
        self.assertEqual(d["c"], 'say "hi"')


class FieldTest(unittest.TestCase):
    def test_cash(self):
        self.assertEqual(ca.parse_cash("$1,000,000"), 1000000)
        self.assertEqual(ca.parse_cash("$1.2 million"), 1200000)
        self.assertEqual(ca.parse_cash("$500K"), 500000)
        self.assertEqual(ca.parse_cash("0"), 0)
        self.assertIsNone(ca.parse_cash("TBD"))
        self.assertIsNone(ca.parse_cash(None))
        self.assertIsNone(ca.parse_cash(True))

    def test_money_mentions(self):
        self.assertEqual(ca.money_mentions("Up to $50,000 in prizes and $2.5 million total"), [50000, 2500000])
        self.assertEqual(ca.money_mentions("$100,000 for Start a SUD Startup"), [100000])
        self.assertEqual(ca.money_mentions("$5 Bonus"), [5])
        self.assertEqual(ca.money_mentions(None), [])

    def test_dates(self):
        self.assertEqual(ca.parse_when("05/16/2019 04:59 PM"), "2019-05-16T16:59")
        self.assertEqual(ca.parse_when("01/24/2020 5:00 PM"), "2020-01-24T17:00")
        self.assertEqual(ca.parse_when("12/01/2026 12:00 AM"), "2026-12-01T00:00")
        self.assertEqual(ca.parse_when("12/01/2026 12:30 PM"), "2026-12-01T12:30")
        self.assertEqual(ca.parse_when("2021-07-04"), "2021-07-04")
        self.assertIsNone(ca.parse_when("13/45/2020"))
        self.assertIsNone(ca.parse_when("soon"))
        self.assertIsNone(ca.parse_when(None))

    def test_fiscal_years(self):
        self.assertEqual(ca.fiscal_year("2019-12-11T10:30"), 2020)
        self.assertEqual(ca.fiscal_year("2020-09-30"), 2020)
        self.assertEqual(ca.fiscal_year("2020-10-01"), 2021)
        self.assertIsNone(ca.fiscal_year(None))
        self.assertEqual(ca.parse_fy("FY20"), 2020)
        self.assertEqual(ca.parse_fy("FY 2021"), 2021)
        self.assertIsNone(ca.parse_fy("n/a"))

    def test_authority(self):
        self.assertEqual(ca.authority_bucket("America COMPETES Act"), ca.COMPETES)
        self.assertEqual(ca.authority_bucket("15 U.S.C. § 3719"), ca.COMPETES)
        self.assertEqual(ca.authority_bucket("Procurement competition"), "other authority")
        self.assertEqual(ca.authority_bucket(None), "not stated")

    def test_types_and_text(self):
        self.assertEqual(ca.challenge_types("Creative (multimedia &amp; design)"),
                         ["Creative (multimedia & design)"])
        self.assertEqual(ca.challenge_types("Something new"), ["Something new"])
        self.assertEqual(ca.challenge_types(None), [])
        self.assertEqual(ca.clean_text("<p>Hello&nbsp;<b>world</b></p>"), "Hello world")
        self.assertEqual(ca.clean_text("{{ site.baseurl }}/x"), "/x")
        self.assertEqual(ca.split_agency("Department of Labor - Veterans' Employment and Training Service"),
                         ("Department of Labor", "Veterans' Employment and Training Service"))


class RecordTest(unittest.TestCase):
    def test_magquest_cash_from_tagline(self):
        r = ca.make_record(fm(MAGQUEST), PATH_A, "abc123")
        self.assertEqual(r["id"], 1012)
        self.assertEqual(r["title"], "MagQuest")
        self.assertEqual((r["department"], r["sub_agency"]),
                         ("Department of Defense", "National Geospatial-Intelligence Agency"))
        self.assertIsNone(r["cash_usd_field"])
        self.assertEqual((r["cash_usd"], r["cash_source"]), (1200000, "tagline"))
        self.assertEqual((r["start"], r["end"]), ("2019-03-21T09:00", "2019-05-16T16:59"))
        self.assertEqual((r["end_year"], r["fiscal_year"], r["fiscal_year_reported"]), (2019, 2019, None))
        self.assertEqual(r["types"], ["Scientific"])
        self.assertEqual(r["authority"], "not stated")
        self.assertIs(r["prize"], True)
        self.assertEqual(r["challenge_gov_url"], "https://www.challenge.gov/challenge/magquest/")
        self.assertEqual(r["archive_url"], "https://github.com/GSA/challenges-and-prizes/blob/abc123/"
                                           "_archive/root/_all-challenges/1012-magquest.md")

    def test_veterans_record_and_no_personal_data(self):
        r = ca.make_record(fm(VETERANS), PATH_B, "abc123")
        self.assertEqual(r["id"], 1085)
        self.assertEqual(r["department"], "Department of Labor")
        self.assertEqual(r["partners_federal"], "Department of Veterans Affairs, Department of Defense")
        self.assertIsNone(r["partners_non_federal"])
        self.assertIsNone(r["external_url"])
        self.assertEqual((r["cash_usd"], r["cash_source"], r["cash_usd_field"]), (1000000, "field", 1000000))
        self.assertEqual(r["types"], ["Software and apps", "Analytics, visualizations, algorithms"])
        self.assertEqual((r["start"], r["end"]), ("2019-12-11T10:30", "2020-01-24T17:00"))
        self.assertEqual((r["end_year"], r["fiscal_year"], r["fiscal_year_reported"]), (2020, 2020, 2020))
        self.assertEqual(r["authority"], ca.COMPETES)
        dumped = json.dumps(r).lower()
        self.assertNotIn("jane", dumped)
        self.assertNotIn("example.gov", dumped)

    def test_build_records_dedupes_and_skips_unparsed(self):
        files = [(PATH_A, MAGQUEST), (ca.ARCHIVE_DIR + "/1012-magquest-copy.md", MAGQUEST),
                 (PATH_B, VETERANS), (ca.ARCHIVE_DIR + "/9-empty.md", "no front matter here")]
        records, duplicates, unparsed = ca.build_records(files, "abc123")
        self.assertEqual([r["id"] for r in records], [1012, 1085])
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(unparsed, ["9-empty.md"])


class SummaryTest(unittest.TestCase):
    def setUp(self):
        files = [(PATH_A, MAGQUEST), (PATH_B, VETERANS), (ca.ARCHIVE_DIR + "/7-no-dates.md", NO_DATES)]
        self.records, _, _ = ca.build_records(files, "abc123")
        self.s = ca.summarize(self.records[1:], source={"commit": "abc123", "files": 2})

    def test_totals(self):
        s = self.s
        self.assertEqual(s["challenges"], 2)
        self.assertEqual(s["cash_usd_total"], 2200000)
        self.assertEqual(s["cash_usd_field_total"], 1000000)
        self.assertEqual(s["cash_from_tagline"], 1)
        self.assertEqual(s["cash_missing"], 0)
        self.assertEqual(s["status"], {"closed": 2})
        # MagQuest: Mar 21 09:00 -> May 16 16:59 is 56 days; Veterans: Dec 11 -> Jan 24 is 44.
        self.assertEqual(s["window_days_median"], 50.0)
        self.assertEqual(s["cset_check"]["challenges"], 1)

    def test_by_year_and_department(self):
        s = self.s
        self.assertEqual(s["by_year"], [
            {"year": 2019, "challenges": 1, "cash_usd": 1200000, "tagline_usd": 1200000, "cash_missing": 0},
            {"year": 2020, "challenges": 1, "cash_usd": 1000000, "tagline_usd": 0, "cash_missing": 0},
        ])
        self.assertEqual([d["department"] for d in s["by_department"]],
                         ["Department of Defense", "Department of Labor"])
        self.assertEqual(s["by_authority"], {"not stated": 1, ca.COMPETES: 1})
        self.assertEqual(s["largest"][0]["id"], 1012)

    def test_unknown_year_and_non_prize(self):
        self.assertEqual(self.records[0]["id"], 7)
        s = ca.summarize(self.records)
        self.assertEqual(s["by_year"][-1],
                         {"year": "unknown", "challenges": 1, "cash_usd": 0, "tagline_usd": 0, "cash_missing": 1})
        self.assertEqual(s["non_prize"], 1)
        self.assertEqual(s["by_authority"]["not stated"], 2)
        self.assertEqual(s["by_type"]["not stated"], 1)

    def test_markdown(self):
        md = ca.summary_markdown(self.s)
        self.assertIn("| 2019 | 1 | 1,200,000 | 1,200,000 | 0 |", md)
        self.assertIn("| 2020 | 1 | 1,000,000 | 0 | 0 |", md)
        self.assertIn("| 1012 | MagQuest | Department of Defense | 2019 | 1,200,000 (tagline) |", md)
        self.assertIn("with AI agents", md)


class DownloadTest(unittest.TestCase):
    def test_resolve_and_list(self):
        self.assertEqual(ca.resolve_commit("staging", get_json=lambda url: {
            "sha": "abc", "commit": {"tree": {"sha": "T0"}}}), ("abc", "T0"))
        trees = {
            "T0": {"tree": [{"path": "_archive", "type": "tree", "sha": "T1"},
                            {"path": "README.md", "type": "blob", "sha": "x"}]},
            "T1": {"tree": [{"path": "root", "type": "tree", "sha": "T2"}]},
            "T2": {"tree": [{"path": "_all-challenges", "type": "tree", "sha": "T3"}]},
            "T3": {"tree": [{"path": "1085-vec.md", "type": "blob", "sha": "c"},
                            {"path": "notes.txt", "type": "blob", "sha": "b"},
                            {"path": "1012-magquest.md", "type": "blob", "sha": "a"}]},
        }
        paths = ca.list_archive("T0", get_json=lambda url: trees[url.rsplit("/", 1)[1]])
        self.assertEqual(paths, [PATH_A, ca.ARCHIVE_DIR + "/1085-vec.md"])

    def test_download_uses_cache(self):
        calls = []

        def getter(url):
            calls.append(url)
            return MAGQUEST.encode("utf-8")

        with tempfile.TemporaryDirectory() as cache:
            first, failed = ca.download([PATH_A], "abc", cache, delay=0, getter=getter)
            second, _ = ca.download([PATH_A], "abc", cache, delay=0, getter=getter)
        self.assertEqual(calls, ["https://raw.githubusercontent.com/GSA/challenges-and-prizes/abc/"
                                 "_archive/root/_all-challenges/1012-magquest.md"])
        self.assertEqual(failed, [])
        self.assertEqual(first, second)
        self.assertEqual(first[0], (PATH_A, MAGQUEST))

    def test_download_failure_is_recorded(self):
        def getter(url):
            raise OSError("boom")

        files, failed = ca.download([PATH_A], "abc", None, delay=0, getter=getter)
        self.assertEqual(files, [])
        self.assertEqual(failed, ["1012-magquest.md (boom)"])


class MainTest(unittest.TestCase):
    def test_main_from_local_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = os.path.join(tmp, "src"), os.path.join(tmp, "out")
            os.makedirs(src)
            for name, text in (("1012-magquest.md", MAGQUEST), ("1085-vec.md", VETERANS)):
                with open(os.path.join(src, name), "w", encoding="utf-8") as f:
                    f.write(text)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ca.main(["--src", src, "--out", out]), 0)
            with open(os.path.join(out, "archive.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["count"], 2)
            with open(os.path.join(out, "archive.csv"), encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], list(ca.CSV_FIELDS))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[2][ca.CSV_FIELDS.index("types")],
                             "Software and apps; Analytics, visualizations, algorithms")
            self.assertTrue(os.path.exists(os.path.join(out, "summary.md")))


if __name__ == "__main__":
    unittest.main()
