# Returns Manager — Cube Buildathon 04

An operational agent that inspects photos of a returned package and produces an **evidence-backed decision record**:

1. **Identity** — is this the SKU that was sold? (look-alike aware)
2. **Completeness** — are the catalogue's parts all present? Which are missing?
3. **Condition** — graded on **Amazon's published condition scale** (no invented grades)
4. **Disposition** — `restock`, `refurbish`, `liquidate`, `dispose` or `pending_review`

Every check is `PASS`, `FAIL` or `UNCERTAIN`, carries a confidence and cites the photo it is based on. Ambiguous evidence goes to a human; the agent never guesses. Operators can override any decision; the agent's original decision and the override (who / when / why) are both kept.

> The original challenge brief is in [`docs/CHALLENGE.md`](docs/CHALLENGE.md). Design details: [`ARCHITECTURE.md`](ARCHITECTURE.md). Contradictions found in the provided data: [`docs/FINDINGS.md`](docs/FINDINGS.md).

```
Identity: PASS | Completeness: FAIL (missing: usb cable) | Condition: Used - Good | Disposition: REFURBISH
```

---

## Why this matters operationally

At a returns bench the bottleneck is not opening boxes, it is **judgement**: each operator decides identity, completeness and grade slightly differently, shifts disagree, and the reasoning is not written down. That produces (a) sellable stock sent to liquidation, (b) wrong-item / empty-box returns restocked as good inventory, and (c) no evidence for the downstream Recovery Manager to claim against.

This agent makes the judgement **consistent** (one published scale, one deterministic rule table), **fast** (one model call per return), and **recorded** (a structured evidence record per unit, keyed by `unit_id` so the Recovery Manager can consume it).

---

## Quick start (Windows, macOS, Linux)

Requirements: **Python 3.10+**. No other packages are required (standard library only). Optional: `pip install pillow` to shrink very large photos before they are sent to the model (the web UI already shrinks photos in the browser).

```bash
git clone https://github.com/klu-2200031174/cube26-rtn-0094-klu-2200031174.git
cd cube26-rtn-0094-klu-2200031174

# 1. configuration
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
#    then open .env and paste your key after GEMINI_API_KEY=

# 2. check the key and model
python -m returns_agent check

# 3. start the operator UI
python -m returns_agent serve
#    open http://127.0.0.1:8000  -> click "Demo: Alpha"
```

Get a Gemini API key at <https://aistudio.google.com> → **Get API key**. Keys live only in `.env`, which is git-ignored.

No key? Set `LLM_PROVIDER=offline` in `.env`: the full workflow runs, but every case is honestly marked `UNCERTAIN` and routed to review.

### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` or `offline` |
| `GEMINI_API_KEY` | — | your key (never commit it) |
| `GEMINI_MODEL` | `gemini-3.5-flash` | vision model id; `check` lists what your key can call |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite` | tried in order if the main model is unavailable or over quota |
| `MODEL_TIMEOUT_S` | `90` | per-request timeout |
| `ORG_TOKENS` | demo tokens | `org_id:token` pairs; the token decides which org you are |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | web server |
| `VAR_DIR` | `var` | SQLite DB + stored photos (git-ignored) |

---

## Using it

### Operator UI (`python -m returns_agent serve`)
1. Sign in with an org token (demo buttons for `org_demo_alpha` / `org_demo_bravo`).
2. Pick the **original order** — the expected product and its parts list are shown.
3. Add 1–8 photos: one overview with **all contents laid out**, plus close-ups of labels and any damage.
4. **Run inspection** → disposition banner, the four checks with verdict / confidence / photo-cited evidence, component table, damage list.
5. **Override** any disposition, grade or verdict with a mandatory reason. The agent's decision stays in the record; the audit trail shows every event.
6. Download the evidence record as JSON, or check its content hash.

### Command line
```bash
python -m returns_agent inspect --org org_demo_alpha --order ORD-DEMO-90001 --images box.jpg contents.jpg
python -m returns_agent findings     # contradictions detected in the reference data
python -m returns_agent eval         # run the evaluation set (see eval/README.md)
python -m unittest discover -s tests -v
```

### HTTP API (all calls need `Authorization: Bearer <org token>`)
| Method & path | Purpose |
|---|---|
| `GET /api/orders` | orders of the caller's org |
| `POST /api/inspections` | `{order_id, operator_label, operator_note?, images:[{data_base64}]}` → evidence record |
| `GET /api/records` · `GET /api/records/{id}` | list / fetch records |
| `POST /api/records/{id}/override` | `{field, revised, reason, operator_label}`; `field` = `disposition`, `condition_grade` or `check:<key>` |
| `POST /api/records/{id}/retry` | re-run the model on stored photos (after a model failure) |
| `GET /api/records/{id}/audit` · `/verify` | append-only audit trail · content-hash check |
| `GET /api/images/{image_id}` | photo, only for the owning org |

---

## Inputs

| Input | Where |
|---|---|
| Product catalogue (SKU, ASIN, visual description, parts with essential/replaceable flags, look-alikes, hygiene flag) | `reference/catalogue.json` |
| Original orders | `data/returns_sample.csv` (organiser sample) + `reference/demo_orders.csv` |
| Condition definitions (quoted from Amazon, with source URLs) | `reference/condition_scale.json` |
| Disposition rules + confidence thresholds | `reference/disposition_rules.json` |
| Returned-item photographs | uploaded per inspection |

**Demoing with your own objects:** the catalogue is synthetic. Edit an entry's `visual_description` / `parts` to match an object you actually have (e.g. your headphones), then use the matching order in `reference/demo_orders.csv`.

## Test inputs

- `tests/test_agent.py` — 31 unit tests: all ten brief scenarios (with scripted model output), evidence guards, fail-open + retry, overrides, tenant isolation over the real HTTP API, rule-table determinism.
- `eval/` — held-out photo evaluation set, two-labeller labels and the harness (see `eval/README.md`). Results: `eval/results/report.md`.
- `docs/sample_evidence_record.json` — an illustrative record (generated from scripted model output, not a real inspection).

## Limitations (honest)

- Accuracy is bounded by the photos: a part hidden inside a closed case is `NOT_VISIBLE` → `UNCERTAIN`, by design. Expect a meaningful review rate.
- Identity is visual only (no barcode/serial decoding). Look-alikes that differ only in text the camera cannot read will be `UNCERTAIN`.
- The catalogue, orders, look-alike lists and rule thresholds are synthetic / chosen by us; they are not Amazon rules. Thresholds should be tuned on labelled data from a real site.
- Condition is judged from the outside; the agent cannot test function (does the lamp turn on?).
- `content_hash` detects that the agent-authored part of a record changed; it is **not** tamper-proof (no signing, no external anchoring).
- Org tokens in `.env` are a simple demo auth scheme, not production identity management. Photos are stored unencrypted on local disk.
- Model output is non-deterministic even at temperature 0; disposition rules are deterministic given the model's observations.
