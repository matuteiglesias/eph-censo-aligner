# Real-vintage integration handoff: EPH acquisition → semantic plane → Census sample → encuestador

## Purpose

This note freezes the current cross-repository data-flow boundary before the first real-vintage semantic approval.

The active graph is:

```text
microdatos-EPH-INDEC
  publicdata.eph-microdata@1
            │
            ├──────────────┐
            ▼              │
   eph-censo-aligner       │
 semantic review/mapping   │
            │              │
            │              ▼
            │        samplerCensoARG
            │   research.census-frame@1
            │   research.census-target-year-sample@2
            │              │
            └──────┬───────┘
                   ▼
          encuestador-de-hogares
      statistical transport / welfare
```

The sampler does not depend on semantic feature approval in order to select households. The aligner does not own sample identity. `encuestador-de-hogares` is the convergence point: it consumes the exact EPH evidence, the approved semantic feature plane and the exact Census sample/scoring payload.

## Current producer contracts

### EPH

Producer: `matuteiglesias/microdatos-EPH-INDEC`

Artifact: `publicdata.eph-microdata@1`

One immutable quarter release contains source-faithful normalized tables under `household/`, `individual/` and possibly `other/`, plus `output-manifest.json` and source provenance. The producer deliberately does not own EPH/Census harmonization, feature engineering, modeling cohorts or model targets.

For semantic review, the aligner must bind the exact EPH release ID, quarter and file/hash identities. It may inspect source columns and category support, but it must not silently promote a historical mapping merely because the names match.

### Census donor frame / sampled scoring population

Producer: `matuteiglesias/samplerCensoARG`

Artifacts:

- `research.census-frame@1`
- `research.census-target-year-sample@2`

The frame preserves Census donor payload and stable relational identities. The v2 sample fixes the selected household/person namespace, complete membership, target-year sampling semantics and design metadata. `selection_probability` and `design_inverse_probability_weight` are audit/design quantities and are not candidate semantic features.

For the first real CPV-2010 path, a full-payload v2 sample provides:

```text
manifest.json
qa.json
selection.parquet
person_membership.parquet
vivienda.parquet
hogar.parquet
persona.parquet
```

The aligner may use the frame or sampled payload to inspect Census fields. Consequential scoring must ultimately bind the exact sample release consumed by `encuestador-de-hogares`.

## First real-vintage goal

Do not attempt to approve the historical 23-variable bridge all at once.

The first useful result is a **minimal source-backed shared feature plane** sufficient to execute one bounded real EPH experiment and, later, one bounded Census scoring pass.

Candidate selection should be driven by the active `encuestador-de-hogares` experiment architecture, not by historical RFC completeness.

For each requested external predictor, record:

1. canonical concept;
2. exact EPH release/file/source field(s);
3. exact Census frame/sample release and source field(s);
4. question/definition evidence when available;
5. universe and reference-period differences;
6. category-domain/value support observed in the actual files;
7. directional recode or deterministic derivation;
8. known loss/ambiguity;
9. semantic class (`shared_observable`, `derived_shared`, `stage_target`, `unsupported`, `research_only`);
10. reviewer status.

Real-vintage approval must remain fail-closed for unsupported fields.

## Required local evidence packet

The first local pass should not copy complete private Census payload into Git. Produce only small metadata/schema evidence and keep real microdata under local controlled storage.

Record the following paths/outputs for review:

### EPH evidence

For one exact quarter release:

- release directory path;
- `output-manifest.json`;
- individual normalized file name and SHA-256;
- household normalized file name and SHA-256;
- headers / column names;
- row counts;
- category/value summaries only for the small requested feature subset;
- confirmation that `CODUSU` and `NRO_HOGAR` exist on the required side(s), or exact actual household join keys if they differ.

### Census evidence

For one validated real `research.census-frame@1` and one `research.census-target-year-sample@2` full-payload release:

- frame release ID and manifest hash;
- frame counts and vintage;
- sample release ID and target year;
- selected household/person counts;
- schema/column names of `persona.parquet`, `hogar.parquet`, `vivienda.parquet`;
- stable sample/frame ID fields;
- category/value summaries only for the small requested feature subset;
- no raw rows unless a tiny non-sensitive example is explicitly required for debugging.

## Approval boundary

A green local extraction/validation result is **not** semantic approval.

The sequence is:

```text
producer release valid
    ↓
exact schemas observed
    ↓
minimal candidate mapping reviewed
    ↓
semantic feature-plane release
    ↓
encuestador real EPH training qualification
    ↓
exact Census scoring qualification
```

The aligner may approve semantic comparability. `encuestador-de-hogares` separately decides target-period admissibility, statistical transport validity and whether a donor-vintage feature belongs in a particular welfare-period experiment.

## Near-term implementation rule

Do not build a generic all-vintage ingestion framework before the first real handoff. Prefer a bounded adapter that consumes the exact producer manifests and emits explicit evidence. Generalize only after the 2024/2025 EPH + CPV-2010 path is proven.

## Legacy

Historical mappings, code and RFC inventories are review clues only. They are not compatibility requirements and do not need numerical or artifact parity with any old produced output.
