# Codex work packet — Batch 1: EPH–Census crosswalk release v1

## Mission

Turn the existing bidirectional EPH–Census aligner into a versioned, fixture-tested crosswalk product whose mappings, supported vintages, losses, ambiguities, and outputs are inspectable.

Do not redesign the statistical concepts. Characterize and harden the implementation that already exists in `aligner/`, then expose its limits honestly.

## Why this matters

This repository represents a real methodological seam: EPH and Census variables can sometimes be translated into a common contract, but they are not automatically statistically or conceptually equivalent. Downstream preprocessing and modeling need an executable mapping release rather than implicit notebook assumptions.

## Read first

1. Read all applicable `AGENTS.md` files.
2. Read `README.md`, `SYSTEM.yaml`, `notas.md`, the current `Makefile`, package metadata, every module under `aligner/`, all mappings, and all tests.
3. Inspect the 2025 implementation history only to understand intent; current code and tests are the source of truth.
4. Treat the README's CLI examples and the current placeholder Makefile as separate facts: the former describes intended behavior, while the latter proves the portfolio command surface is not yet implemented.

## Authority and boundaries

This repository owns:

- its common data model;
- EPH-to-Census and Census-to-EPH mappings;
- recoding, collapsing, conditional, override, and validation rules;
- mapping-release metadata;
- alignment outputs and loss reports.

It does not own:

- official EPH or Census definitions;
- source microdata acquisition;
- geographic-boundary authority;
- income targets, features, or models;
- poverty methodology;
- a claim that translated concepts are equivalent.

## Required deliverables

### 1. Implementation characterization

Create `docs/CROSSWALK_CHARACTERIZATION.md` describing:

- the actual CDM fields and types;
- both transformation directions;
- the CLI's real flags and defaults;
- mapping file formats and loading order;
- joins, overrides, clipping, collapsing, and validation behavior;
- deterministic and nondeterministic surfaces;
- current tests and uncovered behavior;
- current supported source vintages, or an explicit statement that they are unknown.

Record observed behavior before modifying it.

### 2. Reproducible environment

Establish a truthful installation with pinned or bounded dependencies and a clean-check path. Avoid unnecessary packaging churn, but make installation and invocation unambiguous.

Replace the placeholder Make targets with real commands equivalent to:

```bash
make install
make check
make test
make smoke
make release-fixture
```

Requirements:

- `make check` is cheap, offline, and non-mutating outside temporary paths;
- `make smoke` aligns bounded EPH and Census fixtures in both directions;
- `make release-fixture` emits a deterministic fixture release and reports.

### 3. Representative fixtures

Create small synthetic fixtures covering:

- a direct rename/exact mapping;
- a value recode;
- a many-to-one collapse;
- a conditional rule;
- a missing source column;
- an unsupported category;
- an ambiguous or lossy mapping;
- a geographic join or override where current code supports one;
- stable identifiers needed to compare output rows.

Fixtures should demonstrate structure and failure behavior, not imitate confidential records.

### 4. Mapping registry

Introduce a machine-readable registry for every mapping family. Each entry must include, where applicable:

- mapping ID and version;
- transformation direction;
- source dataset and vintage;
- target contract version;
- source and target variables;
- transformation class;
- status;
- evidence or source note;
- known loss or ambiguity;
- reviewer status.

Use a controlled status vocabulary such as:

```text
exact
renamed
recoded
collapsed
conditional
derived
ambiguous
unmapped
unsupported
```

Do not label a mapping `exact` merely because the codes happen to match.

### 5. Variable-level report

For every run, emit a variable-level mapping report with:

- input presence;
- selected rule;
- output presence and type;
- records affected;
- unmatched source values;
- collapsed values;
- nulls introduced;
- validation failures;
- unsupported or skipped variables.

### 6. Row-level and aggregate loss reports

Emit bounded reports for:

- unmatched records;
- unmatched categories;
- ambiguous rules;
- duplicate or conflicting mappings;
- records removed or invalidated;
- information collapsed into broader categories;
- changes in missingness and domain coverage.

The default report must avoid dumping full real microdata. Prefer counts and sampled identifiers under explicit limits.

### 7. Deterministic output contract

Define and test:

- output column order;
- row-order policy;
- identifier preservation;
- data types and null representation;
- stable category normalization;
- deterministic report ordering;
- output naming.

Rerunning a fixture with the same inputs and mapping version must produce identical file hashes.

### 8. Release manifest

A fixture or real alignment release must contain:

- schema version;
- release ID;
- direction;
- source dataset identity and vintage;
- input file hashes;
- mapping-registry version and hash;
- CDM version and hash;
- command and Git commit;
- output file hashes;
- row and column counts;
- references to loss and ambiguity reports;
- reviewer/approval status.

### 9. Human review packet

Create `docs/MAPPING_REVIEW_REQUIRED.md` listing every consequential mapping that requires methodological approval, especially:

- many-to-one collapses;
- conditional recodes;
- geography overrides;
- mappings with different question wording or universe;
- derived variables;
- rules that alter missingness or sample membership.

Do not mark these approved on Matías's behalf.

## Ordered execution

1. Characterize the current code and mappings.
2. Make installation and existing tests reproducible.
3. Replace the placeholder Make surface with truthful commands.
4. Add fixtures and characterization tests around existing behavior.
5. Add the mapping registry without silently changing semantics.
6. Add deterministic outputs and loss reports.
7. Add the release manifest and fixture release.
8. Reconcile README and `SYSTEM.yaml` with demonstrated behavior.
9. Present consequential mappings for human review.

## Integration contract

The release should be consumable as a versioned artifact, conceptually:

```text
artifact:research.eph-census-crosswalk@1
```

Do not require consumers to read this repository's working tree through a sibling path. A consumer should receive an explicit release directory or package plus its manifest.

## Human checkpoints

Stop for review before:

- changing a CDM field's meaning;
- approving a collapsed or conditional mapping;
- changing supported source vintages;
- changing sample membership;
- resolving an ambiguity through an undocumented assumption;
- declaring two survey concepts equivalent;
- changing downstream model features.

## Non-goals

- No model training or feature selection.
- No source acquisition.
- No poverty computation.
- No expansion to every EPH and Census variable.
- No wholesale rewrite merely to adopt a new framework.
- No real-data release committed to Git.
- No automatic approval of mappings.

## Stop conditions

Stop rather than guess when:

- source wording or universe cannot be established;
- a mapping depends on an unknown vintage;
- two rules conflict;
- a transformation changes substantive meaning;
- a geographic override lacks evidence;
- current tests and code disagree in a way that cannot be resolved mechanically.

## Acceptance criteria

```text
clean installation succeeds
real Make targets replace the placeholders
both alignment directions pass fixture tests
mapping registry identifies source vintages and mapping statuses
loss, unmatched, collapse, and ambiguity reports are emitted
a fixture release is byte-deterministic across reruns
release manifest hashes inputs, mappings, CDM, reports, and outputs
consequential mappings remain explicitly pending human review
README and SYSTEM declarations match the proven behavior
```

## Completion report

The final response and PR description must include:

- exact commands run;
- fixture scenarios covered;
- mapping counts by status;
- unsupported variables and vintages;
- deterministic-release hashes;
- every consequential mapping awaiting Matías's decision;
- confirmation that no equivalence, model, or poverty claim was introduced.
