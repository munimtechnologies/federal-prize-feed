# federal-prize-feed

Open U.S. federal prize competitions as **JSON, CSV, an Atom feed, a calendar of deadlines and a
short Markdown digest**.

Challenge.gov, the federal government's shared prize portal, was retired on March 30, 2026.
Its archive moved to [GSA/challenges-and-prizes](https://github.com/GSA/challenges-and-prizes)
(read-only since then). Active challenges are now published as ordinary web pages on
[USA.gov](https://www.usa.gov/find-active-challenge), with no API and no feed, and many
agencies post challenges only on their own sites. This project collects them in
machine-readable form, so that newsletters, universities, small businesses and civic groups
can track federal prizes without checking each agency's site by hand.

## Use the data

| File | What it is |
|---|---|
| [`data/digest.md`](data/digest.md) | One page to read: what is new, what closes in the next 30 days, what opens later, and everything else by closing date |
| [`data/active.json`](data/active.json) | Every challenge USA.gov lists, plus challenges posted only on agency pages: sponsor, open and close dates, challenge types, prize lines, cash total, contact, application link, status, source |
| [`data/active.csv`](data/active.csv) | The same as a spreadsheet |
| [`data/feed.xml`](data/feed.xml) | Atom feed, one entry per challenge. Add it to any feed reader to see new challenges |
| [`data/deadlines.ics`](data/deadlines.ics) | One all-day event on each closing date. Subscribe in Google Calendar, Outlook or Apple Calendar using the raw URL below |
| [`data/federal-register.json`](data/federal-register.json) | Federal Register notices from the last 12 months whose titles name a challenge, prize or competition (some are closed; they often announce challenges USA.gov never lists) |
| `data/changes.json` | Challenges added, removed or changed at each refresh, newest first (created by the first refresh) |
| [`agency_challenges.json`](agency_challenges.json) | The hand-checked list of agency-only challenges that is merged into `active.json` |
| [`sources.md`](sources.md) | Every page we know of that posts federal challenges, and which are stale |

Raw URLs to point tools at:

```
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/active.json
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/active.csv
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/feed.xml
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/deadlines.ics
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/federal-register.json
https://raw.githubusercontent.com/munimtechnologies/federal-prize-feed/main/data/digest.md
```

On 2026-10-14 the feed held **29 open or upcoming challenges with about $60.2 million in stated
cash prizes**: 16 from USA.gov and 13 that only agency pages list. The agency-only ones include
AHRQ's Healthcare Choice and Competition Challenge (up to $11.8 million, Phase 1 closes
October 26, 2026), AHRQ's Clinical Evidence Synthesis Transformation Challenge (up to $5.85
million, opens January 11, 2027), the National Library of Medicine's two SPARK AI-retrieval
challenges ($250,000 each), three NIH disability and community-engagement prizes, the 2027 NIA
Start-Up Challenge, FHWA's highway workers memorial design challenge and three NASA challenges.

## Run it yourself

Python 3.8+, standard library only.

```
python federal_prizes.py --out data              # fetch everything and write the files
python federal_prizes.py --from-json data/active.json --out data   # rebuild offline
python -m unittest -v                            # tests, no network
```

It fetches the USA.gov listing plus one page per challenge, waiting 10 seconds between
requests as USA.gov's robots.txt asks, and identifies itself with a `federal-prize-feed`
User-Agent. It then makes two requests to the public Federal Register API. If it finds no
challenges on USA.gov (for example after a site redesign) it writes nothing and exits with
status 1; if the Federal Register is unreachable it keeps the previous notices file.
`generated_at` in `active.json` shows when the data was last built. A GitHub Action
(`.github/workflows/refresh.yml`) is meant to rebuild it daily.

Each record looks like this:

```json
{
  "slug": "xtech-search-10",
  "title": "xTech|Search 10",
  "sponsor": "U.S. Army xTech",
  "start_date": "2026-09-10", "end_date": "2026-10-19", "end_time_et": "17:00",
  "types": ["Ideation", "Software and application development"],
  "prizes": ["Cash prize: $1,000,000"],
  "cash_prize_usd": 1000000,
  "apply_url": "https://xtech.army.mil/competition/xtechsearch10/",
  "source": "usa.gov",
  "status": "open"
}
```

`cash_prize_usd` is the cash amount the listing states (a "Total cash prizes" line when
there is one). Follow-on contracts, SBIR awards and non-cash prizes are not counted.
`status` is `open`, `upcoming` or `closed` on the day the file was built. `source` is
`usa.gov` or `agency page`; agency entries drop out by themselves once their end date passes.

## Limits

- USA.gov calls its list "select" challenges. The agency list is checked by hand and will
  miss some; `sources.md` lists the pages we watch. Please open an issue for anything missing.
- Some agency sites (nih.gov, ahrq.gov) refuse automated reads, so a few agency entries were
  checked against the agency's own press release or challenge platform instead of the
  challenge page itself. `sources.md` says which.
- Dates are copied as the pages show them (Eastern Time where a time is given). Phase and
  registration deadlines inside a challenge can be earlier than its end date, so always read
  the official rules before you apply.
- The Federal Register search matches notice text, then keeps notices whose titles name a
  challenge, prize or competition; it can miss notices with other titles.
- This is not an official government product and is not affiliated with GSA, USA.gov or the
  Federal Register. The underlying listings are U.S. government works.

## Changes

- 0.3.0: `data/digest.md` (new, closing soon, opening later); 10 more agency-only challenges
  from AHRQ, NIH (NLM, NIA, NIDDK, the Disability Health Research Program) and FHWA.
- 0.2.0: agency-only challenges (`agency_challenges.json`), Atom feed, Federal Register prize
  notices, change log, `source` field.
- 0.1.0: USA.gov listing as JSON, CSV and iCalendar (never released on its own).

## About

Made by MV2 of Munim, Inc. The code and data were produced with AI agents working in his
name and are published in the open. Corrections and new sources are welcome as issues or
pull requests.

Apache-2.0 license (code). Contact: munimversion2@gmail.com
