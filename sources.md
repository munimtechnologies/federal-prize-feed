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
| DARPA challenges | https://www.darpa.mil/research/challenges |
| HeroX, government challenges (hosts many agency prizes, e.g. NIH, DOE American-Made) | https://www.herox.com/crowdsourcing-projects/government |
| DOE Office of Electricity, American-Made prizes | https://www.energy.gov/oe/our-american-made-challenges |
| Challenge.gov archive, challenges before 2026 (read-only) | https://github.com/GSA/challenges-and-prizes/tree/staging/_archive/root/_all-challenges |
| GSA guidance for challenge managers | https://www.gsa.gov/technology/government-it-initiatives/prize-competitions |

Notes from checking these pages (2026-10-13 and 2026-10-14):

- NASA's page lists challenges USA.gov does not. Three open ones are in
  `agency_challenges.json`: the TechLeap Orbital Clarity Challenge (registration closes
  October 28, 2026), the Lunar Grounding Challenge (closes January 15, 2027) and the 2026
  Space Apps Challenge (November 14-15). NASA's ORBIT Challenge 2027 and RASC-AL 2027 are
  for college students; they are not included yet.
- xTech's page shows xTech|Search 10 as the only xTech competition still taking
  submissions; the others, including xTech|Kinetic Reach (still on USA.gov until November 30),
  say their submission window has closed.
- DARPA's page lists Triage (finals only), Lift (returns summer 2028), the Surgical
  Competition and the D2 Sprint; the last two are on USA.gov.
- The DHS page lists one open competition (Ready, Set... ID the Biothreat, closes October 14,
  2026), the same one USA.gov lists.
- The HHS page still links its "current" challenges to challenge.gov addresses, which no
  longer resolve. Treat that page as stale.
- nih.gov/challenges and HeroX block or script-render their listings, so a plain HTTP fetch
  returns nothing useful.
- Most Federal Register prize notices cite 15 U.S.C. 3719 (the America COMPETES prize
  authority), which is why the script searches for "3719". In the last year that search
  surfaced, among others, NASA's Deep Space Food Challenge: Mars to Table, HHS's EHIgnite
  Challenge, DOT's Combating Human Trafficking in Transportation Impact Awards and FHWA's
  memorial design challenge, none of which were on USA.gov's list.
- The last tool that did this job, paulsmith/challenge.gov-scraper, read challenge.gov's
  homepage and so stopped working when the site was retired.

Know another page that lists federal challenges? Please open an issue.
