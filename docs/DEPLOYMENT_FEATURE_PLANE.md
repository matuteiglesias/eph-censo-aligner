# Deployment feature plane — vocabulary only

This note defines a small vocabulary for the future audit of variables that may participate in an EPH-trained, Census-scored model. It does **not** approve any real EPH/Census vintage, mapping, model or inference run.

## Categories

### `shared_observable`

A concept directly observable in both approved source vintages after an explicit, reviewed semantic mapping. Differences in wording, universe, reference period, category support and missingness must still be recorded.

### `derived_shared`

A concept that can be deterministically derived on both sides from approved source fields using the same declared semantic rule. The derivation must not use a target, future information or source-only latent label.

### `stage_target`

A concept observed in EPH and potentially useful as an intermediate supervised target, but not required as a Census input. A deployable staged model may predict it from shared observables. If later stages use the prediction, training evidence must avoid substituting observed labels where inference would see predictions.

### `unsupported`

A concept that cannot currently be constructed defensibly from the target Census vintage, or whose mapping remains ambiguous/pending. It cannot be an external input of a promoted Census-deployable model.

### `research_only`

A variable intentionally allowed in EPH-only experiments or oracle/leakage/sensitivity studies but excluded from the deployment input plane.

## Audit record

A future real-vintage audit should record, for every candidate feature:

- canonical concept name;
- EPH source field(s) and vintage;
- Census source field(s) and vintage;
- category from the vocabulary above;
- recode/derivation rule;
- universe and reference-period differences;
- category losses and missingness behavior;
- geography dependence, if any;
- reviewer/evidence status.

## Deployment invariant

A promoted Census-deployable model must be a pure function of an approved canonical feature frame made only from `shared_observable` and `derived_shared` inputs. `stage_target` variables may be internal learned outputs, not required external Census columns.

## Stop conditions

Do not promote a variable because names look similar, because a legacy script used it, or because a synthetic fixture can execute. Real-vintage approval requires source evidence and methodological review under `MAPPING_REVIEW_REQUIRED.md`.
