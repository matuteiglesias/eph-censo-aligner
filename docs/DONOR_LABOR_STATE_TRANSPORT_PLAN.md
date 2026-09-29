# Donor labor-state semantic handoff — implementation plan

Status: implementation-ready design, 2026-09-29.

## Mission

Make donor-vintage labor status explicit in the EPH↔Census semantic feature plane so downstream transport studies can distinguish:

```text
donor-vintage observed labor state
!=
target-period current labor state
```

Current real donor: **CPV-2010**.

Future donor: **CPV-2022**, through the same policy-driven compiler after its own source-backed semantic review.

This repo owns semantic meaning and recoding. It does not decide whether stale donor labor state is statistically useful at a target welfare period.

## Current problem

The existing CPV-2010 real plane exposes the `ESTADO` ↔ `CONDACT` concept, but historical/current model code can too easily treat Census `CONDACT` as if it were current-period labor truth.

The longitudinal study needs an explicit donor-labor field whose clock cannot be confused.

## Canonical handoff

Add a model-facing field/role conceptually equivalent to:

```text
donor_condact
donor_condact_vintage
donor_condact_semantic_status
```

Exact naming may follow existing contract conventions.

Required properties:

- source is the exact Census donor frame/sample;
- value recoding is governed by the real review policy;
- donor vintage is explicit;
- target welfare period is not embedded in the source value;
- semantic class may remain shared/observed where justified;
- transport-time role is downstream-consumer-owned and must not be promoted here to "current".

The EPH-side current `ESTADO/CONDACT` remains distinguishable from the Census donor value.

## CPV-2010 first

Extend/review the existing exact EPH-2024-Q3 ↔ CPV-2010 policy and reusable compiler so a materialized scoring plane can preserve the donor labor observation explicitly rather than aliasing it into a timeless `CONDACT`.

Do not fork a special 2010 pipeline.

Required QA:

- source code/value inventory;
- EPH↔CPV semantic recode evidence;
- age/universe rules;
- missing/unknown category accounting;
- exact sample-person identity preservation;
- no silent row drops;
- no target-period relabeling.

## CPV-2022 later

The same conceptual output should be available once a source-backed CPV-2022 review policy exists.

Do not make CPV-2022 a prerequisite for the current 2010-based research program.

The downstream transport model must bind:

```text
census_frame_vintage
donor_labor_vintage
welfare_period
elapsed_quarters_since_donor
```

but only the first two are source/semantic facts owned here.

## Important scientific gate: training analogue

A Census donor-state feature is not directly observed for arbitrary EPH 2017-2026 rows.

Therefore this repo must **not** create a fake EPH `donor_condact` by copying current EPH `CONDACT`.

The downstream L11/L12 study requires a separate EPH panel/transition analogue. This aligner only makes the Census donor observation unambiguous.

## Cloud work packet — C3

Deliver:

1. explicit donor-labor field in the real semantic-plane contract;
2. CPV-2010 policy evidence/recoding update;
3. manifest metadata for donor vintage;
4. exact identity and missing-category QA;
5. fixture coverage showing donor/current clock separation;
6. consumer documentation showing how `encuestador-de-hogares` receives the field;
7. no statistical persistence or welfare claims.

Where the existing artifact contract can carry source-vintage metadata without a schema break, prefer backward-compatible extension.

## Local work packet — L3

After C3 and after an exact CPV-2010 sample exists for a target-year run:

1. materialize the real CPV-2010 semantic scoring plane;
2. verify donor `CONDACT` coverage;
3. emit category/missingness by age/region;
4. verify exact sample person/household IDs;
5. hand the immutable plane to `encuestador-de-hogares`.

This local gate may run on one bounded sample first. It must not create welfare predictions.

## Definition of done

The current Census labor observation can be consumed downstream as an explicitly stale donor-vintage state, with no semantic ambiguity and no implication that it is current labor status. The same contract is ready for a future CPV-2022 policy.

## Non-goals

- no labor-state transition model;
- no KL/moment calibration;
- no use of aggregate unemployment rates;
- no welfare model;
- no claim that CPV-2010 labor state is useful for 2017-2026.
