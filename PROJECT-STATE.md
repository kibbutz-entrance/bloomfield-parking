# Parking project — current state

- Canonical repository: kibbutz-entrance/bloomfield-parking, branch main, public.
- Public URL: https://kibbutz-entrance.github.io/bloomfield-parking/
- User explicitly approved public website and public code on 2026-11-02. The earlier approval block was resolved; no publication approval remains pending. GitHub sudo/email authentication was completed through secure browserAuth; do not record credentials or codes.
- Existing Claude design reused. כנראה is beside the status, and the thin באזור label is removed. Preserve this design.
- Previous implementation: six official feeds across sportpalace.co.il, football.org.il, maccabi-tlv.co.il and sportlv.co.il. Required feeds: stadium_sports, stadium_culture, maccabi, city. IFA works locally but returns 403 from GitHub runners; it remains supplementary with original cache age and errors exposed. Do not treat cached IFA records as freshly checked.
- Backend: GitHub Actions refreshes and deploys at minutes 13 and 43 of every hour, plus pushes and manual runs. Publication gate PAGES_ENABLED was removed after approval. GitHub Pages uses Actions and HTTPS.
- Reliability: no synthetic fallback fixtures or invented kickoff times. Date/time/venue/cancellation disagreement stays uncertain; missing home venue stays uncertain. This old green rule was replaced in the 2026-11-03 audit below. Parking is an estimate based on published events, not space occupancy or an official traffic closure.
- Validation: 17 Python tests and 17 Node tests passed locally and on GitHub. Production run 41530238351 completed build and deploy successfully. Fresh core data was pulled at 2026-11-02T21:38:59+00:00. Public HTML and games.json were checked. Nov 6 14:00 agrees among stadium, city and Maccabi.
- No paid subscriptions, API keys or account upgrades were introduced. No outstanding blockers. Future work should inspect the current source and current Actions run rather than reconstruct from old snapshots.

## Scope confirmed and event-source research — 2026-11-02

- User confirmed parking target: Kibbutz Galuyot 21, Tel Aviv. Parking pressure may extend from Bloomfield and nearby large events.
- Default language changed to Hebrew for new visitors regardless of browser locale; an explicitly saved English preference is preserved. Commit 53f0da488d4c0d9a28f01918ebdd7b80648a586b.
- New candidate sources researched but NOT integrated: Gagarin, Kibbutz Galuyot 13 (https://gagarin.co.il/events/; Nov 7 Anime & K-POP festival 18:00); Haoman 17, Abarbanel 88 (https://www.haoman17.com/events; Nov 6, 13, 20); Duplex, HaShah 10 (https://duplexclub.co.il/; Nov 5 at 23:00 and Nov 6 at 23:59).
- Candidate priority is based on proximity and published event activity, not measured attendance or observed parking impact. Add per-venue congestion estimates rather than reusing football windows. Deduplicate simultaneous multi-room parties at the same venue.
- Current automatic coverage still filters Bloomfield. Do not claim comprehensive coverage of all nearby events or that parking predictions are verified facts. Accurate claim: published events from official sources, cross-checked where multiple sources exist, with estimated parking impact and explicit freshness/uncertainty.

## Current architecture — 2026-11-03 audit

- User explicitly requested implementation and publication of a useful probability-based decision engine, plus a senior-level backend audit. No further approval required.
- Seven feeds / five independent publishers, including Haoman 17. Gagarin and Duplex are still NOT integrated (HTTP 403 in the audit environment).
- Empty days can be probable-green for up to one year when >=2 independent stadium schedule publishers are fresh (2 hours), including stadium operator or city. Missing supplemental feeds lower certainty without blanket gray. Dates >14 days carry a provisional warning.
- Current observations supersede failed-source caches within a three-day rescheduling cluster. Current disagreements stay tentative; unique old events remain warnings. Each event exposes evidence, independent publisher count and verification category in games.json.
- Haoman structured blog feed: explicit full body date only, optional published Doors time, per-venue estimated window -60/+360 minutes. Undated posts are excluded and source marked partial; partial feeds can confirm parsed events but cannot prove absence. All pagination is followed and validated with a hard limit; publication order is never assumed to be event order.
- Confirmed congestion remains red if another event is tentative, with warning; gray is reserved for actual planned/contradictory/stale events or inadequate independent fresh coverage.
- No measured parking occupancy or calibrated probability. Preserve original UI design, Hebrew default, inline כנראה and subtle calendar pulse.
- Local validation: 31 Python + 24 Node tests passed; a live pull returned 21 upcoming records including 3 Haoman dates. Production run 41617096002 succeeded (build, tests, pull, commit, Pages deploy). Live JSON at 2026-11-03T10:11:04Z: 4 full feeds, Haoman partial (73 undated historical posts excluded), 2 IFA feeds error403 with original 2026-11-02 success times. Nov6 match corroborated by stadium, city and Maccabi (3 publishers). Browser verified green Feb1 with provisional note, and Nov6 red with separate11:00–16:30 and22:55–24:00 windows; screenshot saved. Follow-up UI labels cached events stale in upcoming rows too.

## User scope correction — Haoman removed

User explicitly requested removing all Haoman 17 parties (star symbols in titles), because their parking impact is unproven. Source, records and cache removed; frontend filters retired events out of old offline snapshots. Current scope: six feeds / four publishers focused on Bloomfield. Do not reintroduce Haoman in future research or automated updates without a new user request. Earlier Haoman notes above are historical.
