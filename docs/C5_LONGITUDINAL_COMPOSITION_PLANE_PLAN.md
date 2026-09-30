# C5 — longitudinal canonical composition plane

Status: implemented and merged via PR #25 on 2026-09-30. Real 37-quarter approval remains the local L3B gate.

## Motivation

The merged C2 longitudinal frame is deliberately source-faithful. The C4 fixture runtime currently names raw EPH variables directly.

That must not become the stabilized scientific boundary.

The existing real CPV-2010 semantic compiler already owns the reviewed EPH↔Census recodes and produced the bounded 2024-Q3 P1-R plane. The longitudinal program needs those semantics exposed as a reusable **canonical composition plane** over 2017-Q1..2026-Q1 without putting recoding logic inside `encuestador-de-hogares`.

This repository owns that semantic layer.

## Contract

Add a versioned artifact conceptually equivalent to:

```text
research.eph-longitudinal-composition-plane/v1
```

Grain: one row per C2 person observation, keyed exactly by C2 `row_id`.

The artifact should contain canonical feature columns plus:

```text
row_id
household_observation_id
panel_household_id
period
region_id
source_release_id
semantic_policy_id
feature_profile_id
semantic_status / QA references
```

It must not contain welfare targets as model inputs.

## Named feature profiles

Do not let downstream code silently invent feature lists.

At minimum expose two named profiles.

### `P0_LONG`

The historical minimal direct baseline, for comparison/compatibility:

```text
CH04 / P02-equivalent sex
CH06 / P03-equivalent age
CH07 relationship/marital-state concept as governed
CH09
CH10
CH12
CH13
CH15
IX_TOT
```

Use canonical names where an approved semantic concept exists. The exact profile registry should make raw-source aliases explicit.

### `P1R_NOLAB_LONG`

The richer bounded P1-R information plane **excluding current individual labor state**.

Starting canonical concept set:

```text
IX_TOT
P02 P03 P05
P07 P08 P09 P10
V01
H05 H07 H08 H09 H10 H12 H13 H14 H15
PROP
```

This is deliberately P1-R minus `CONDACT`.

Do not silently add `H06`, `H11`, `H16` or any concept whose current review decision is unresolved/needs-judgment.

Important: this profile is a **research composition candidate**, not automatically a claim that every donor-vintage Census state is temporally current or deployment-safe. Preserve each concept's semantic decision and temporal-role metadata.

## EPH longitudinal semantics

The current exact review policy is bound to EPH-2024-Q3 + CPV-2010. Do not simply apply it to 37 quarters and call all vintages reviewed.

C5 should separate:

1. reusable canonical recode definitions;
2. period/source support evidence;
3. real longitudinal approval.

The cloud implementation may build a fixture-backed compiler and support inventory. The real 2017-2026 support decision belongs to local gate L3B.

For each concept and period, record:

```text
raw source field
observed raw support
canonical support
unexpected codes
null/special handling
review status
temporal role
```

Unknown codes fail closed.

## Census compatibility

The named profile registry must be reusable by the existing CPV-2010 semantic-plane compiler so Gate E scoring can select the same canonical profile on Census rows.

Do not create a second Census mapping system.

Donor labor remains separate through C3's explicit donor-labor handoff.

## Cloud work packet — C5

Implement:

1. canonical longitudinal composition-plane contract;
2. named `P0_LONG` and `P1R_NOLAB_LONG` profile registry;
3. compiler consuming C2 `research.eph-longitudinal-analysis-frame/v1`;
4. exact row/household identity preservation;
5. period×concept support inventory;
6. fail-closed unexpected-code/schema behavior;
7. manifest/checksum lineage to exact C2 parent and semantic policy/profile;
8. fixtures spanning multiple periods/schema-support cases;
9. compatibility hook so existing CPV-2010 materialization can select the same named profile;
10. docs clarifying semantic comparability versus temporal admissibility.

Do not train welfare or labor-transition models.

## Local work packet — L3B

After C5 lands and L2 produces the real longitudinal EPH frame:

1. materialize both named profiles over all 37 periods;
2. audit raw/canonical supports by period;
3. adjudicate any historical category/schema change from source evidence;
4. fail closed on unsupported concepts/periods;
5. freeze one real longitudinal composition-plane release;
6. verify the profile selected for L10 exists on every intended model row;
7. hand exact release identity/hash to `encuestador-de-hogares`.

## Relation to C3 / L3A

C3 owns donor-vintage labor semantics.

L3A materializes the real CPV-2010 donor-labor handoff.

C5/L3B owns the longitudinal canonical composition plane.

They are related but independently testable.

## Definition of done

Downstream L10/L11/L12 can consume named canonical composition features without containing raw EPH↔Census recode logic, and the same profile identity can later be selected on exact Census scoring rows.

## Non-goals

- no claim that CPV-2010 state equals target-period state;
- no individual current labor reconstruction;
- no KL anchor;
- no welfare model;
- no forecast/nowcast.
