# Build log

| Date (IST) | What changed | Why |
|---|---|---|
| 2026-09-28 | Project skeleton: reference data (catalogue, Amazon condition scale with sources, rule table), single-call Gemini inspection, deterministic checks and rules, evidence record, SQLite store with tenant isolation, overrides and audit log, operator UI, CLI, eval harness, 26 unit tests | Core workflow first, per the brief |
| 2026-09-28 | Documented contradictions in the sample data (docs/FINDINGS.md) | Honesty rule 3 |
| 2026-09-28 | First live Gemini runs: added retries/back-off and more fallback models after HTTP 503 (model overloaded); fail-open kept the case | Live test |
| 2026-09-28 | Bug: completeness returned PASS (0/0) for a SKU missing from the catalogue -> now UNCERTAIN | Found in live earbuds test |
| 2026-09-28 | New rule R09B: if unseen parts could change the disposition, send to review | Earbuds test: left earbud not verifiable while other parts missing |
| 2026-09-28 | Consistency fix: same earphone photos gave DISPOSE once and RESTOCK once (model flipped between 'lightly used' and 'opened'). Hygiene rule R08 now keys on sealed vs not sealed | Live repeat test |
| 2026-09-28 | Redesigned operator UI (decision pipeline, evidence links, record stats); household items added to catalogue | Usability |
| 2026-09-28 | Latency fix: with the primary model overloaded, retries could keep an operator waiting for minutes. Busy models are now skipped immediately, total wait capped at 75 s, unfinished inspections show a Retry button | Live use: inspections felt stuck |
| 2026-09-28 | Catalogue fix: earbuds listed as separate "left" and "right" parts, which photos cannot tell apart -> one part "earbuds (pair of 2)" | Live earbuds test |
| 2026-09-29 | Evaluation set: 50 held-out cases, one phone photo each, 10 scenarios (eval/eval_set.csv, eval/photo_map.csv) | Evaluation rule: 50 unseen units |
| 2026-09-29 | Catalogue: chargers split into white Samsung (white cable) and OPPO (white adapter, black cable); a flip-lid water bottle replaces the perfume bottle, which was not available | Match the real items photographed |
| 2026-09-29 | Two label sets (A and B) recorded; expected dispositions derived from the labels with the same rule table as the agent (eval/derive_dispositions.py) | Disposition accuracy measures rule-consistent outcomes |
| 2026-09-29 | Fix: evaluation crashed on Windows when removing its temporary database (file still open) -> database closed first, cleanup errors ignored | First full eval run on Windows |
| 2026-09-29 | Evaluation run on 50 units: identity 91.5% (0 wrong items accepted), completeness 100% on right-item cases, disposition 73%, review rate 34%; failure modes in docs/EVAL_REPORT.md | Evaluation |
