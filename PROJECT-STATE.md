# Parking project — continuation state

- Canonical repository: kibbutz-entrance/bloomfield-parking, branch main; created private on 2026-11-02.
- Goal: preserve Claude's existing design, put כנראה beside status, remove the thin באזור label, host on GitHub with reliable automatic official data collection.
- Source: uploaded bloomfield-parking-repo.zip. Existing UI reused, not rebuilt.
- Data: six official feeds across sportpalace.co.il, football.org.il, maccabi-tlv.co.il and sportlv.co.il; no API key. IFA works from the local environment but returned 403 from GitHub runners. It is supplementary, with errors and original cache age exposed. Required core feeds are stadium sports, stadium culture, Maccabi, and City Sports API. City API is paginated and uses UTC event timestamps. Backend refresh is scheduled every 30 minutes. Frontend rejects stale all-clear states.
- Validation: 17 Python parser/failure tests, 17 Node reliability/timezone tests, and browser checks of Hebrew UI and source status. See tests/.
- Publication blocker: automated approval review rejected creating a PUBLIC repository because the original hosting request did not explicitly authorize public visibility. A PRIVATE repository was created as a safer alternative. Do not turn it public or publish via another route to bypass that rejection. Obtain explicit approval for public repository/code and public website.
- GitHub Pages settings were inspected. The current account requires public visibility or a paid upgrade for this private repository. No paid upgrade is authorized or needed for the proposed public route.
- Next after user approval: make the existing repo public; enable Pages via Actions; set repository Actions variable PAGES_ENABLED=true; run workflow; verify remote update, deploy and deployed UI. Preserve the existing repo identity and all source logic.
- PAGES_ENABLED is deliberately unset, so deployment remains disabled while the approval is pending. No hosted website URL has been claimed.
