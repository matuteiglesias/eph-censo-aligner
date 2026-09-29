# Donor labor-state semantic handoff

Status: implemented contract for Cloud packet C3.

## Purpose

The real semantic plane distinguishes two different observations:

```text
EPH ESTADO at the EPH quarter
!=
Census CONDACT at the donor Census vintage
```

For the current exact policy, the donor is CPV-2010. The same compiler is intended
to accept CPV-2022 once a separate source-backed review policy exists.

## Backward-compatible extension

The feature-plane manifest schema remains:

```text
research.eph-census-semantic-feature-plane/v1
```

The legacy P1-R common plane continues to contain `CONDACT` for compatibility.
C3 does not reinterpret that field as current target-period truth. Instead, the
manifest gains an explicit Census-only donor-labor handoff and two additional
payload files:

```text
census_donor_labor_state.parquet
donor_labor_qa.json
```

Because the reviewed CPV-2010 policy changed materially, its exact release ID is
advanced to:

```text
eph-cpv2010-semantic-plane-2024q3-v2
```

The review-policy schema itself remains v1; no generic compiler schema break is
required.

## Donor artifact

`census_donor_labor_state.parquet` preserves exact identity columns:

```text
row_id
household_id
sample_person_id
sample_household_id
frame_person_id
frame_household_id
frame_dwelling_id
```

and adds:

```text
donor_condact
donor_condact_vintage
donor_condact_semantic_status
```

For the current policy, `donor_condact_vintage=2010`.

`donor_condact` is the reviewed canonical recode of raw Census `CONDACT` on
the common age-14+ labor universe. It is never labeled as current labor state at
the EPH period or at a later welfare period.

`donor_condact_semantic_status` distinguishes reviewed observed values from
rows that are missing or outside the reviewed universe.

## QA

`donor_labor_qa.json` records:

- exact donor vintage and EPH clock side by side;
- raw source-value counts and canonical value counts;
- raw and canonical support;
- expected special codes mapped to null;
- unexpected source codes and impossible canonical values;
- canonical null count;
- age-universe eligible/outside counts;
- exact row-count preservation;
- unique sample-person and canonical row identity;
- an explicit statement that no EPH donor-state training analogue was built.

A non-null canonical donor labor state below the reviewed minimum age is a hard
failure.

## Training analogue boundary

This repository does not create:

```text
EPH donor_condact := current EPH ESTADO
```

That shortcut would erase the temporal problem under study.

The later longitudinal work in `encuestador-de-hogares` must build an honest
stale-state analogue from repeated-wave EPH observations. The aligner supplies
only the Census donor observation and its semantic/source clock.

## CPV-2022 compatibility

The implementation reads the donor vintage from
`policy.clocks.census_vintage`. There is no code branch for 2010.

A future CPV-2022 policy must independently pin:

- exact Census frame/sample parents;
- `census_vintage=2022`;
- source codebook evidence;
- labor-state universe and recoding;
- donor-labor handoff policy metadata.

If those reviews pass, the same compiler emits the same donor handoff shape with
`donor_condact_vintage=2022`.

## L3 real materialization gate

The subsequent local materialization must verify on the real CPV-2010 sample:

1. exact policy/frame/sample parent identities;
2. exact donor handoff row count equals exact Census person membership count;
3. unique sample and frame person identities;
4. raw `CONDACT` value inventory and canonical `donor_condact` inventory;
5. age-14+ universe accounting and all missing/special categories;
6. no non-null donor state outside the reviewed universe;
7. donor vintage remains 2010 on every row;
8. no target-period relabeling;
9. immutable manifest and payload hashes before handoff to
   `encuestador-de-hogares`.

Passing those checks establishes semantic/source custody only. It does not
establish persistence, predictive usefulness, transport validity, or welfare
validity.
