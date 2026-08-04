# Cross-repository artifact integration

## Topology

The crosswalk is an optional immutable input to EPH preprocessing, not a mandatory
stage in a distributed pipeline. `income-modeling-eph` must consume an exported
release directory and must not invoke this repository or read its working tree.
The same rule applies independently to geography releases.

## Shared envelope

`manifest.json` implements `research-artifact-manifest/v1` with the common fields
`artifact_type`, `release_id`, `status`, `producer`, `created_at_utc`,
`method_version`, `data_vintage`, `inputs`, `files`, `reports`, and `limitations`.
Repository-specific direction, entity, mapping/CDM hashes, row counts, and review
state remain extensions. Every file entry carries path, SHA-256, and byte size.
Status has the shared meaning: `synthetic` uses no real source data, `candidate`
has not completed methodological review, `reviewed` records completed review, and
`approved` is eligible for approved-mode consumption. This repository currently
emits only `synthetic`; it never promotes status automatically.

The release timestamp is the producer commit timestamp rather than wall-clock
time, preserving byte determinism. `producer.dirty_worktree` records the state
captured before output creation; candidate or approved publication policy should
require `false`.

## Compatibility before execution

The self-contained `compatibility.json` declares
`research.eph-census-crosswalk/v1`, optional geography, supported synthetic input
vintages, the `research.eph-preprocessing/v1` consumer contract, and approval-mode
policy. `python -m aligner.integration` rejects an unsupported/new manifest schema,
wrong artifact type or vintage, manifest/file checksum mismatch, unsafe/missing
file, mismatched upstream manifest identity, incompatible geography identifier
contract, synthetic crosswalk in a real run, or pending methodology in approved
mode.

## Consumer-owned Batch 2 fixture

`income-modeling-eph` should own the integration fixture because optional omission
and annual-input provenance are consumer behavior. It should copy immutable
synthetic release directories from each producer (or construct contract fixtures),
never import their source trees, and test:

1. valid EPH source accepted;
2. checksum mismatch rejected;
3. unsupported vintage rejected;
4. crosswalk omitted successfully;
5. incompatible crosswalk vintage rejected;
6. incompatible geography identifier contract rejected;
7. pending release rejected in approved mode; and
8. complete provenance reproduced in the annual-input manifest.

This producer covers its side with contract-envelope, checksum, vintage,
geography-contract, synthetic/real, and approval-policy tests. It deliberately
does not make the model, EPH source, or geography repositories runtime dependencies.
