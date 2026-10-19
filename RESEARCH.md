# 2026 House & Senate vote tracker — data source research
Researched Oct 19, 2026 (ET). Election Day: Tue Nov 3, 2026. Every item below was checked by fetching it live unless marked "per docs/search".

## 1. Early / absentee / mail vote

| Source | URL | Granularity | Format | Update cadence | Terms | Status |
|---|---|---|---|---|---|---|
| **UF Election Lab 2026 Early Voting tracker** (Dr. Michael McDonald) | https://election.lab.ufl.edu/early-vote/2026-early-voting/ | State (49 jurisdictions incl. DC listed; **AL and NH not listed**); district for 21 states | **CSV**, not documented as an API but used by the dashboard: `https://election.lab.ufl.edu/data-downloads/earlyvote/2026/US.csv`, `<ST>_cd.csv` (district × county rows), `house_tossup_races.csv` | Daily (some states several times a day; others weekly or less, see `last_update`) | Page says: "In some cases data are compiled from data obtained directly from state election officials and are not in the public domain." No license stated → **attribute and ask UF (election-lab@ufl.edu) before republishing publicly**. Archive datasets need a free login; some need a paid subscription. | **Working, used in prototype** |
| Same: fields | — | request/accept(mail returned)/inperson/voted totals; party registration (dem/rep/none), age buckets, gender, race/ethnicity where the state provides them | — | — | Party = voter registration, **not votes** | — |
| District files available (`<ST>_cd.csv`, Oct 19) | — | AZ, CA, CO, CT, GA, IA, ID, KS, MD, ME, MI, NC, NE, NJ, NV, OH, OK, PA, RI, UT, VA | CSV, cd labels are inconsistent ("001", "Congressional 1", "CONGRESSIONAL DISTRICT 1", "1.0"), so they get normalized | — | — | Some files don't sum to the state total (e.g. GA district mail 36,811 vs state 40,236); some rows have no district |
| States with no 2026 data posted in the tracker yet (Oct 19) | — | AK, AR, LA, MO, NY, SC, TX, WV (`last_update` 8/12/2026, all zeros); WA has requests only | — | — | — | Gap: these states often release data only once in-person early voting starts, or not at all |
| AP Elections API — "advance turnout" | https://developer.ap.org/ap-elections-api/ | State-by-state requested/sent/returned, demographics, in-person, historical comparisons (per docs) | JSON API, key required | Continuous | Paid; pricing not published (elections_api_info@ap.org) | Not tested (no key) |
| DDHQ | https://www.decisiondeskhq.com/products , https://votes.decisiondeskhq.com/pricing | Its Votes product lists "early voting and breakdowns" | Web; API is enterprise | — | Votes Pro $24.99 individual (web, through the 2026 cycle); API/enterprise: contact sales | Not tested |
| State SOS / county voter files | per state (UF links each state's source in `data_source` column of US.csv) | Often county/precinct; some states give individual-level absentee files (e.g. NC, GA, FL) | CSV/zip, mixed | Daily in most states that publish | Varies by state | Better to rely on UF, which already does the aggregation |

## 2. Election-night results

| Source | Coverage | Format / access | Cost | Notes |
|---|---|---|---|---|
| **Open America results feed** https://openamerica.io/elections/api/ | **About 22 states** whose official feeds it can read; House, Senate, Governor | `GET /elections/results.json?year=2026&office=House|Senate` JSON, no key, CORS `*`, ETag, poll every 60 s while `live` | Free, no quota (asks for a descriptive User-Agent and backoff) | Passes through official counts; **makes no race calls or projections**. Live-tested: 2026 payload is empty for now (`live:false`); `year=2024` returns a replay of 2024 results (198 House / 11 Senate races) for testing. Third-party hobby/independent service, so plan a fallback. **Prototype uses it.** |
| Clarity / Scytl ENR (state and county sites, e.g. GA and many counties) | States/counties that use Clarity | `results.enr.clarityelections.com/{ST}/{electionID}/current_ver.txt` → `/{ver}/json/en/summary.json`, `reports/detailxml.zip` | Free (public sites) | Election IDs are only known once the 2026 site is posted. Libraries: openelections/clarify, washingtonpost/elex-clarity |
| State SOS JSON/CSV results pages | Each of 50 states separately | All different; some sites are HTML only, some block scrapers | Free | Building a full 50-state scraper set in 2 weeks is a lot of work and fragile |
| civicAPI https://civicapi.org | Claims worldwide live results and race calls | JSON, no key | Free | Not tested in depth; documentation for House/Senate fields not reviewed |
| **AP Elections API** | All races nationwide, county level, **race calls**, advance turnout | JSON, API key, per-minute quota | Paid, contact AP (no public price) | Industry standard; contracts usually take time to arrange, which matters with 2 weeks left |
| **Decision Desk HQ API** https://docs.decisiondeskhq.com | All races, race calls, vote history, forecasts, balance of power | OAuth JSON API v4/v5, has a testing environment | Enterprise, contact sales | Same timing caveat |
| Historical: MIT Election Data + Science Lab | House 1976–2024 by district; Senate; 2024 precinct returns | CSV (Harvard Dataverse, GitHub MEDSL/2024-elections-official), CC0 | Free | Good for 2024 comparison columns; not live |
| Historical: OpenElections | Precinct-level certified results by state (GitHub openelections-data-XX) | CSV | Free | Not live |

## 3. Race list & candidates

| Source | What | Format | Notes |
|---|---|---|---|
| **Wikipedia** "2026 United States House of Representatives elections" / "2026 United States Senate elections" | All 435 districts with PVI, incumbent(s), status, candidates; 35 Senate races (33 Class 2 + FL and OH Class 3 specials), 11 outlet ratings, poll-closing times | HTML via MediaWiki parse API | CC BY-SA 4.0. **Used in prototype** (435 + 35 parsed). Crowd-edited, so pin `revid` (stored in JSON) and spot-check. Includes mid-decade redistricting (seats with two incumbents, e.g. TX, CA-40, UT-04). |
| FEC API https://api.open.fec.gov/v1/candidates/ | Every candidate who **filed** with the FEC (e.g. 305 active 2026 Senate candidates) | JSON; `DEMO_KEY` works but limit is 10 requests (`x-ratelimit-limit: 10`) | Includes many people who are not on the November ballot; good for IDs/finance, not for the ballot list. Get a free api.data.gov key for real use. |
| Ballotpedia | Ballot-qualified candidates | Web; data API is paid | Not used |

## 4. Main gaps
1. **No free, complete, nationwide live results feed with race calls.** Free options cover part of the country (Open America ~22 states) or need a scraper for each state. Full coverage plus calls means AP or DDHQ (paid).
2. Early vote by **congressional district** exists for only 21 states, and some of those files are incomplete.
3. Early vote for AL and NH is missing from the tracker, and 8 more states (AK, AR, LA, MO, NY, SC, TX, WV) have no 2026 numbers posted yet.
4. Party-registration splits only exist in party-registration states, and they show registration, not vote choice.
5. UF data redistribution terms aren't stated, so get permission or link back prominently.
