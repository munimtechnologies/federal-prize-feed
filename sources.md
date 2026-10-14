# Where federal prize competitions are posted now

Challenge.gov was retired on March 30, 2026. USA.gov lists "select" active challenges at
https://www.usa.gov/find-active-challenge (that is what `federal_prizes.py` reads). Agencies
also post challenges on their own pages. USA.gov's "Other challenges from the federal
government" page (https://www.usa.gov/other-government-challenges, last updated March 19,
2026) points to these:

| Agency | Page |
|---|---|
| Department of Health and Human Services | https://health.gov/grants/challenge-competitions |
| Department of Homeland Security, S&T | https://www.dhs.gov/science-and-technology/prize-competitions |
| NASA | https://www.nasa.gov/prizes-challenges-and-crowdsourcing/ |
| National Institutes of Health | https://www.nih.gov/challenges |
| U.S. Army xTech | https://xtech.army.mil/competitions/ |
| U.S. Geological Survey (mapping challenges) | https://www.usgs.gov/core-science-systems/ngp/tnm-corps/mapping-challenges |

Other places federal challenges appear:

| Where | Page |
|---|---|
| Federal Register notices (read automatically into `data/federal-register.json`) | https://www.federalregister.gov/documents/search?conditions%5Bterm%5D=3719 |
| NIH/NIDDK Challenge Management Platform (NLM SPARK, NIDDK challenges) | https://repository.niddk.nih.gov/data-challenge |
| AHRQ challenges | https://www.ahrq.gov/healthcarechoice/index.html and https://www.ahrq.gov/si/sihealthcareimprovement.html |
| Bureau of Reclamation prize competitions | https://www.usbr.gov/research/challenges/ |
| DARPA challenges | https://www.darpa.mil/research/challenges |
| HeroX, government challenges (hosts many agency prizes, e.g. NIH, DOE American-Made) | https://www.herox.com/crowdsourcing-projects/government |
| DOE American-Made program (prize list loads by script) | https://americanmadeprogram.org/compete/prizes-and-competitions |
| DOE Office of Electricity, American-Made prizes | https://www.energy.gov/oe/our-american-made-challenges |
| Challenge.gov archive, challenges before 2026 (read-only) | https://github.com/GSA/challenges-and-prizes/tree/staging/_archive/root/_all-challenges |
| GSA guidance for challenge managers | https://www.gsa.gov/technology/government-it-initiatives/prize-competitions |

Notes from checking these pages (2026-10-13 and 2026-10-14):

- NASA's page lists challenges USA.gov does not. Three open ones are in
  `agency_challenges.json`: the TechLeap Orbital Clarity Challenge (registration closes
  October 28, 2026), the Lunar Grounding Challenge (closes January 15, 2027) and the 2026
  Space Apps Challenge (November 14-15). NASA's ORBIT Challenge 2027 and RASC-AL 2027 are
  for college students; they are not included yet.
- NIH runs many challenges that USA.gov does not list. nih.gov refuses automated reads, so
  these entries were checked as follows: the two NLM SPARK challenges and the NIDDK Early
  Research Partnership Engagement Challenge against their pages on the NIDDK Challenge
  Management Platform (dates, prize splits, metrics); the SPARK launch against NLM's news
  release and Technical Bulletin; the 2026 NIH Prize for Excellence in Disability Health
  Research, the Advancing the Inclusion of People with Disabilities in Clinical Research
  Challenge and the 2027 NIA Start-Up Challenge against NIH's announcements as quoted in
  search results. Open an issue if any detail differs from the official page.
- AHRQ launched two prize programs in October 2026. ahrq.gov refuses automated reads, so they
  were checked against AHRQ's own press releases (PR Newswire, October 6 and 7, 2026) and
  AHA News (October 8, 2026): the Healthcare Choice and Competition Challenge (up to $11.8
  million; Phase 1 from September 30 to October 26, 2026, 5 PM ET) and the Super
  Intelligence for Healthcare Improvement Initiative (up to $7.95 million), split here into
  the Clinical Evidence Synthesis Transformation Challenge (five $100,000 Phase 1 prizes and
  one $5.35 million prize; submissions January 11 to March 12, 2027) and the SI Tech Sprint
  ($2.1 million; submissions March 1 to September 9, 2027).
- FHWA's memorial design challenge appears only as a Federal Register notice (2026-12440):
  $5,000, entries by email to WZMemorial@dot.gov by October 20, 2026.
- xTech's page shows xTech|Search 10 as the only xTech competition still taking
  submissions; the others, including xTech|Kinetic Reach (still on USA.gov until November 30),
  say their submission window has closed.
- DARPA's page lists Triage (finals only), Lift (returns summer 2028), the Surgical
  Competition and the D2 Sprint; the last two are on USA.gov.
- The DHS page lists one open competition (Ready, Set... ID the Biothreat, closes October 14,
  2026), the same one USA.gov lists.
- The Bureau of Reclamation's "accepting submissions" page says no prize competition is open
  (updated September 9, 2026); Halt the Hitchhiker, Crack the Case and Seal Team Fix are in
  later phases for earlier winners.
- Announced but not open yet, so not in the feed: NSF's two $33 million Grand Research
  Challenge prizes (Quantum+X and synthetic multicellularity, announced October 8, 2026, rules
  not yet published) and EPA's planned crop desiccation challenge (up to $30 million; EPA
  asked for public comment in July 2026).
- The HHS page still links its "current" challenges to challenge.gov addresses, which no
  longer resolve. Treat that page as stale.
- nih.gov, ahrq.gov and HeroX block or script-render their listings, so a plain HTTP fetch
  returns nothing useful. The American-Made program site also loads its prize list by script.
- Most Federal Register prize notices cite 15 U.S.C. 3719 (the America COMPETES prize
  authority), which is why the script searches for "3719". In the last year that search
  surfaced, among others, NASA's Deep Space Food Challenge: Mars to Table, HHS's EHIgnite
  Challenge, DOT's Combating Human Trafficking in Transportation Impact Awards and FHWA's
  memorial design challenge, none of which were on USA.gov's list.
- The last tool that did this job, paulsmith/challenge.gov-scraper, read challenge.gov's
  homepage and so stopped working when the site was retired.

Know another page that lists federal challenges? Please open an issue.
