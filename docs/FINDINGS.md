# Findings: contradictions in the provided material

The rules say "contradictions are findings — raise them, don't silently pick one." These are the ones found while building, with how the agent handles each. `python -m returns_agent findings` re-checks the machine-detectable ones.

## F1: One ASIN used by two different SKUs
`B0DUMMY357` is the ASIN for **SKU-LAMP-LED** (RTN-0014, RTN-0043) and for **SKU-PROT-1KG** (RTN-0038, RTN-0081, RTN-0097). An ASIN should identify exactly one product.
**Handling:** identity is checked against the **SKU's catalogue entry**, not the ASIN alone. The finding is reported by the `findings` command.

## F2: Restocked although the main product is missing (RTN-0038)
`parts_missing = tub` (the protein tub is the product itself), yet `identity_match = yes` and `operator_disposition = restock`. You cannot restock a unit whose main component is absent.
**Handling:** a missing non-replaceable part triggers rule R10 (liquidate). Because only the scoop is visible, identity will usually be FAIL or UNCERTAIN, which goes to review first (R03/R04).

## F3: The same observation gets different dispositions
For `opened_unused` with nothing missing:

| Record | SKU | Operator disposition |
|---|---|---|
| RTN-0009 | PUZZLE-500 | refurbish |
| RTN-0023, RTN-0036 | PUZZLE-500 | restock |
| RTN-0043 | LAMP-LED | restock |
| RTN-0054 | MUG-11 | refurbish |
| RTN-0067 | CABLE-USBC | refurbish |

Identical inputs give different outcomes. This is the operator variance the brief describes.
**Handling:** a deterministic rule table (ARCHITECTURE §5). The same verdicts and grade always give the same disposition.

## F4: A missing part leads to a better outcome than a complete unit
- RTN-0003: PUZZLE-500, `signs_of_use`, **complete** → liquidate.
- RTN-0050: PUZZLE-500, `signs_of_use`, **poster missing** → refurbish.

**Handling:** in our rules a complete Used - Good unit is refurbished (R16). A unit missing one replaceable part is refurbished only if it grades Used - Good or better (R12).

## F5: "Damaged" is not a disposition
Damaged units go to dispose (RTN-0021, RTN-0027, RTN-0099) or liquidate (RTN-0039, RTN-0041, RTN-0093).
**Handling:** damage is recorded with a severity. The disposition depends on the published grade: Unacceptable with severe damage → dispose; Unacceptable otherwise → liquidate; Acceptable → liquidate.

## F6: Hygiene-sensitive items restocked after opening
RTN-0016 (towel), RTN-0030 (face serum) and RTN-0081 (protein powder) are `opened_unused` → restock. Whether opened beauty or food items may be resold depends on marketplace category policy. The sample data is synthetic and cannot be treated as authoritative on this.
**Handling:** the catalogue has a `hygiene_sensitive` flag. Hygiene-sensitive items are restocked **only if factory-sealed / New**; anything opened is disposed (R08). We first tried "dispose only if used", but in a live test the same photos of the same earphones were classed once as `signs_of_use` (DISPOSE) and once as `opened_unused` (RESTOCK). Photos cannot reliably separate "opened" from "lightly used", so the rule no longer depends on that line. This is a policy assumption to confirm against the marketplace's category rules.

## F7: Amazon's scale vs the brief's example
Amazon's guidelines list "missing essential parts" as **unacceptable** for listing. The brief's example grades headphones with a missing USB cable as **Used - Good** and dispositions them **REFURBISH**.
**Handling:** we grade the **physical condition of what is present** and handle missing parts in the completeness check. A missing *replaceable* part leads to refurbish (replace it, then list). A missing *non-replaceable* part leads to liquidate. This reproduces the brief's example while staying consistent with Amazon's rule, because the item is not listed until it is complete again.

## F8: Four dispositions or five?
The problem statement lists four dispositions. The repo README and sample data also use `pending_review`.
**Handling:** we support all five. `pending_review` is used whenever evidence is insufficient (UNCERTAIN) or the item is not the one sold.

## F9: Renewed and Collectible grades
They are on Amazon's published scale, but a returns bench cannot assign them. Renewed needs testing by an Amazon-qualified supplier, and Collectible needs additional collectible value.
**Handling:** they are listed in `reference/condition_scale.json` as excluded, and the agent never outputs them.

## F10: No images, no condition values
`photo_refs` point at files that do not exist, and `amazon_condition` is empty on purpose. The sample CSV therefore cannot be used as an evaluation set.
**Handling:** we built a separate held-out photo set with two labellers (see `eval/README.md`).
