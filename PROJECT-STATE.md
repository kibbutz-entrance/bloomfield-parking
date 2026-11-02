# Parking project — current state

- Canonical repository: kibbutz-entrance/bloomfield-parking, branch main, public.
- Public URL: https://kibbutz-entrance.github.io/bloomfield-parking/
- User explicitly approved public website and public code on 2026-11-02. The earlier approval block was resolved; no publication approval remains pending. GitHub sudo/email authentication was completed through secure browserAuth; do not record credentials or codes.
- Existing Claude design reused. כנראה is beside the status, and the thin באזור label is removed. Preserve this design.
- Six official feeds across sportpalace.co.il, football.org.il, maccabi-tlv.co.il and sportlv.co.il. Required feeds: stadium_sports, stadium_culture, maccabi, city. IFA works locally but returns 403 from GitHub runners; it remains supplementary with original cache age and errors exposed. Do not treat cached IFA records as freshly checked.
- Backend: GitHub Actions refreshes and deploys at minutes 13 and 43 of every hour, plus pushes and manual runs. Publication gate PAGES_ENABLED was removed after approval. GitHub Pages uses Actions and HTTPS.
- Reliability: no synthetic fallback fixtures or invented kickoff times. Date/time/venue/cancellation disagreement stays uncertain; missing home venue stays uncertain. Green requires all core feeds fresh within 2 hours and a date within the 14-day coverage window. Parking is an estimate based on published events, not space occupancy or an official traffic closure.
- Validation: 17 Python tests and 17 Node tests passed locally and on GitHub. Production run 41530238351 completed build and deploy successfully. Fresh core data was pulled at 2026-11-02T21:38:59+00:00. Public HTML and games.json were checked. Nov 6 14:00 agrees among stadium, city and Maccabi.
- No paid subscriptions, API keys or account upgrades were introduced. No outstanding blockers. Future work should inspect the current source and current Actions run rather than reconstruct from old snapshots.
