# Crosswalk implementation characterization (observed before release v1)

## Contract and transformations

The pre-release `cdm.py`, CLI, I/O and validation modules were empty; therefore there was no executable CDM or CLI contract. The two non-empty aligners operated on pandas frames. Their effective minimum household contract was `IX_TOT`, sex, age, activity and agglomeration; the individual path required record keys/age/school attendance/activity. Values were ordinary pandas numeric/object values and missing values were pandas nulls.

EPH→Census filters household rows where `IV1 == 9`, renames a 24-variable subset, collapses split `V21`, `V22`, `V5`, `V11` (argmax) and `V2` (active-suffix list), recodes selected categories, clips `IX_TOT` to 0–8, optionally left-joins `Region` by `DPTO`, applies agglomeration 33/93 overrides, then validates required columns. Its individual route renames `ESTADO`, collapses module flags, recodes `CH15` and `CH09`, clips negative age, changes activity below age 14, changes `CH13` for education categories, optionally enriches geography, casts monetary columns, and validates.

Census→EPH recodes Census-named fields before the reverse rename, clips `H16` to 0–9, optionally joins/overrides geography, casts monetary columns, and validates. The individual route additionally collapses module flags and sets activity to zero below age 14.

## Mapping and command surfaces

No mapping files were present in the checked-out tree, and the code used in-module dictionaries in declaration order. Historical paths existed but were not runtime inputs. Imports were top-level (`from utils`) and worked only under particular path manipulation. The README advertised `--source`, `--target`, `--input`, and `--output`, but `cli.py` was empty. The Makefile was explicitly a failing placeholder. Thus there were no real CLI flags/defaults before this work.

## Joins, recodes, and validation details

Missing rename sources are silently ignored. Recode uses `Series.map`, so unsupported non-null categories become null despite the docstring saying they remain unchanged. Region lookup deduplicates complete `(DPTO, Region)` pairs, not `DPTO` alone, so conflicting lookup rows can multiply records. Overrides are hard-coded and lack cited evidence. Validation checks column presence only; it does not check uniqueness, domain, type, or nullability.

## Determinism and coverage

Column and row order formerly followed input/pandas operation order. Family discovery followed input column order, so ties and list order could vary with input column order. CSV serialization, output naming, reports, hashes, and release metadata were unspecified. Existing tracked test modules were empty at characterization time. Consequently transformations, errors, joins, unsupported values, and determinism were uncovered.

`notas.md` describes candidate EPH eras from 2003 Q3 onward, but those statements were not tied to runnable mappings or fixtures. No Census vintage was identified. Therefore **supported real source vintages are unknown**. Release v1 supports only the explicit synthetic `fixture-v1` vintage and must reject all claimed real vintages pending evidence and review.

## Release hardening added after characterization

The v1 registry treats each direction as an independent rule set; it does not
invert forward mappings to construct reverse mappings. Its executable precedence
key includes direction, entity, vintage, source, target, and priority. Duplicate
precedence or undeclared composition is a release error. Rename assurance remains
explicitly unverified, including lexically identical fields.

Characterization also exposed that household source recodes were formerly called
after their source columns had been renamed, making several declared recodes
unreachable. Release v1 orders governed source recodes before renaming and applies
the individual target rename only after source-side conditional rules. This is
fixture-covered behavior, remains methodologically pending, and must not be read
as approval of the category semantics.

Each successful run now assigns every input row exactly one terminal disposition:
`emitted`, `removed`, `invalid`, `unsupported`, `unmatched`, or `failed`.
Ambiguity, collapse, override, and clipping remain overlapping diagnostic flags,
not terminal states. The loss report includes both counts and the reconciliation
identity `input = emitted + removed + invalid + unsupported + unmatched + failed`,
and requires a zero difference.
