# Demo video plan (about 5 minutes, screen + phone camera)

1. **Problem (30 s).** A returns bench has to answer 4 questions per parcel. Today every operator answers them differently and nothing is recorded. Show `docs/FINDINGS.md` F3: identical `opened_unused` cases got restock in one row and refurbish in another.
2. **Setup (30 s).** Show `.env.example` (no secrets in the repo), then run `python -m returns_agent check` and `python -m returns_agent serve`. Sign in as org Alpha.
3. **Brief example (60 s).** Headphones order, USB cable removed, contents laid out. Result: Identity PASS, Completeness FAIL (usb cable), Used - Good, REFURBISH (rule R12). Click a "photo #n" evidence link to show what the agent cited.
4. **Wrong item (30 s).** Headphones order, mug in the box. Identity FAIL, pending_review (R03).
5. **Look-alike (30 s).** USB-C order, USB-A cable photographed. The result is UNCERTAIN or FAIL, and it is never a confident PASS.
6. **Ambiguous (30 s).** A dark, blurry photo gives UNCERTAIN and goes to review. Explain that refusing to guess is a design choice.
7. **Heavily damaged (20 s).** Unacceptable with severe damage → DISPOSE.
8. **Human override (40 s).** Override a disposition with a reason. Show that the agent's original decision is still in the record, then open the audit trail and run the content-hash check.
9. **Fail-open (20 s).** Set a wrong API key and run an inspection. The case is kept as pending_review; fix the key and click Retry.
10. **Tenancy (20 s).** Switch to org Bravo: zero records, and opening Alpha's photo URL returns 404. Run `python -m unittest` to show all tests passing.
11. **Evaluation (40 s).** Open `eval/results/report.md` and walk through human agreement, per-check FP/FN, review rate, latency and 1–2 failure modes.
