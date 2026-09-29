# Demo video plan (about 5 minutes, screen recording)

Use photos from `eval/photos` (case ids in brackets) so everything shown is real.

1. **Problem (30 s).** A returns bench answers 4 questions per parcel and today every operator answers them differently. Show `docs/FINDINGS.md` F3: the same `opened_unused` case gets restock in one row and refurbish in another.
2. **Setup (30 s).** Show `.env.example` (no secrets in the repo), run `python -m returns_agent check` and `python -m returns_agent serve`, sign in as org Alpha.
3. **Complete item (40 s).** Wireless earbuds order, photo of the open case with both earbuds (E06). Identity PASS, Completeness PASS, grade, disposition and rule. Click a "photo #0" evidence link.
4. **Missing part (40 s).** Water bottle order, bottle without its lid (E14), or OPPO charger order with only the adapter (E18). Completeness FAIL naming the missing part, REFURBISH via rule R12.
5. **Wrong item (30 s).** Samsung charger order, soft toy in the photo (E08). Identity FAIL, PENDING REVIEW (R03).
6. **Look-alike (30 s).** Samsung charger order, OPPO charger with the black cable (E48). The agent must not give a confident PASS.
7. **Ambiguous photo (30 s).** The completely dark vase photo (E42) or the blurry soft toy (E44). UNCERTAIN, sent to review: refusing to guess is a design choice.
8. **Heavily damaged (20 s).** Samsung charger with the taped, burnt cable (E41). Unacceptable, DISPOSE.
9. **Human override (40 s).** Override a disposition with a reason; show the agent's original decision is still in the record; open the audit trail and run the content-hash check.
10. **Fail-open (20 s).** Put a wrong API key in `.env`, restart, run an inspection: the case is kept as pending review; fix the key and click Retry.
11. **Tenancy (20 s).** Switch to org Bravo: zero records; Alpha's photo link returns 404. Run `python -m unittest discover -s tests` to show all tests passing.
12. **Evaluation (40 s).** Open `eval/results/report.md`: labeller agreement, per-check FP/FN, review rate, latency, and 1-2 failure modes from the disputed or wrong cases.
