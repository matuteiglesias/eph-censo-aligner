# L3 — real semantic materialization gates

Status: L3A/L3B executed and complete, 2026-09-30. L3A materialized `eph-cpv2010-semantic-plane-2024q3-v2`; L3B materialized real `P0_LONG` and `P1R_NOLAB_LONG` releases across all 37 quarters with exact C2 row preservation and zero unresolved unexpected/impossible code cells. The optional bounded CPV-2010 profile/scoring proof remains downstream Gate-E work.

This local packet has two independent sub-gates.

## L3A — CPV-2010 donor-labor handoff

Authority:

`docs/DONOR_LABOR_STATE_TRANSPORT_PLAN.md`

Using the merged C3 compiler and an exact CPV-2010 sample/frame:

1. materialize the real semantic plane;
2. materialize `census_donor_labor_state.parquet`;
3. verify exact sample/frame person and household identities;
4. verify donor vintage = 2010 on every row;
5. inspect raw/canonical `CONDACT` supports;
6. inspect missing/special categories by age and region;
7. verify age-14+ universe behavior;
8. verify no target-period relabeling;
9. verify immutable hashes/manifests.

Persist the real handoff release identity and QA receipt.

No persistence or welfare claim is authorized by L3A.

## L3B — longitudinal canonical composition plane

Authority:

`docs/C5_LONGITUDINAL_COMPOSITION_PLANE_PLAN.md`

Prerequisites:

- merged C5;
- real L2 longitudinal EPH frame.

Materialize `P0_LONG` and `P1R_NOLAB_LONG` over 2017-Q1..2026-Q1.

Required audit:

- 37-period row coverage;
- exact C2 row-identity preservation;
- raw/canonical category support per concept×period;
- unexpected-code failures;
- semantic null/special handling;
- temporal-role metadata;
- unresolved concept exclusion;
- profile completeness;
- manifest/checksum lineage.

Any historical concept drift that lacks source-backed adjudication blocks that concept/profile for the affected period; do not guess.

The longitudinal compiler uses the governed `longitudinal_specials_v1.json`
policy for recognized historical survey-special codes. These values become a
canonical null for that feature only; the underlying C2 person row is retained.
The policy is hashed into each immutable release. Unknown codes and substantive
semantic drift continue to fail closed.

## Optional bounded CPV-2010 profile proof

After L3A/L3B, materialize one bounded CPV-2010 scoring plane selecting the same named profile intended for L10 Gate E.

This proves feature identity compatibility only. It does not validate statistical transport.

## Receipt

Persist separate L3A and L3B receipts, each with:

```text
release_id
parent release identities
manifest_sha256
row counts
identity QA
support/category QA
unresolved issues
validation commands/results
```

## Definition of done

L3 is complete when:

- CPV-2010 donor labor exists as an explicit immutable donor-vintage handoff;
- a real 37-quarter canonical EPH composition plane exists under named profiles;
- both are ready for exact downstream binding without semantic recoding inside `encuestador-de-hogares`.
