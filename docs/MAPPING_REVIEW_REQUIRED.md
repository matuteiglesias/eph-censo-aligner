# Mapping review required

**Approval state: pending.** Nothing below is approved on Matías's behalf. Registry entries retain `reviewer_status: pending`.

## Active real-review evidence

The current exact review pair is no longer synthetic-only. It is one **policy instance** of a donor-vintage-neutral compiler:

- EPH release: `eph-2024-q3-3b6a7a15c4af`;
- CPV-2010 frame: `arg-cpv2010-frame-ee6ada167c2d6429`;
- Census sample: `census-sample-2024-0839713eafea8d1b` (`research.census-target-year-sample/v2`, full payload);
- clocks pinned by policy: EPH `2024-Q3`, donor vintage `2010`, sampling target year `2024`.

Machine-native official source semantics for the 23 current candidate concepts are bound in:

- `aligner/codebooks/real_2024q3_cpv2010_23.json`;
- `aligner/codebooks/README.md`;
- `aligner/review_evidence/eph-2024-q3-3b6a7a15c4af.json`;
- `aligner/review_evidence/census-sample-2024-0839713eafea8d1b.json`.

The codebook layer distinguishes raw producer field identity from REDATAM presentation/derived aliases. For example, the real CPV source payload uses raw `P07`, `P08`, `P09`, `P10`, while some REDATAM dictionary views expose names such as `P1707`, `P1808`, `P1909`, `P2010`. Do not rewrite raw producer identities from presentation aliases.

Official source documents are pointers/evidence, not copied manuals. The active EPH register-design PDF and the CPV-2010 database-definitions PDF provide field definitions/codes; the Census basic questionnaire supplies instrument wording, universe and skip logic. A mapping still requires exact-release support and reviewer judgment.

### Donor-vintage consolidation rule

A future CPV-2022 review must not fork the implementation. It supplies a new exact policy/codebook evidence bundle to the same compiler. The policy must pin `census_vintage=2022`, exact frame/sample parents and the sampling target period. Concept names may be reused only when source definitions support the same canonical meaning.

Changing donor vintage does **not** automatically preserve a prior semantic decision or temporal role. It triggers source-backed review, while downstream statistical transport remains outside this repository.

### Semantic compatibility versus statistical support

The real semantic compiler now treats these as different evidence classes:

- **hard semantic violations**: unexpected raw codes after reviewed special handling,
  impossible canonical values, identity/schema/custody failures;
- **nonblocking support diagnostics**: a valid canonical Census category is absent
  from the realized EPH quarter.

The latter must remain visible for downstream transport/support analysis, but it
must not make semantic materialization fail merely because one EPH quarter does
not realize every valid Census category.

For the exact 2024-Q3/CPV-2010 policy, source-era zero/special values outside the
documented substantive question domains are handled explicitly in the policy.
This is not a generic "zero means missing" rule. The current bounded policy
covers only reviewed concepts and preserves unexpected values as hard failures.

EPH CH06=-1 is handled separately as the established infant-age sentinel and
maps to canonical age 0 rather than null.

### Exact-pair residual closure

For the exact 2024-Q3 / CPV-2010 policy, the final observed hard residuals are
handled without widening the generic compiler:

- Census IX_TOT uses exact complete household membership and is validated only
  as a positive integer; no arbitrary upper clipping is applied.
- EPH CH13=0 and II7/II8/II9=0 are treated as exact-release not-applicable
  sentinels.
- EPH CH09=9 and CH10=9 are treated as exact-release missing sentinels because
  they fall outside the documented substantive 1..3 domains.
- Any neighboring unreviewed code remains a hard failure.

These rules belong to this reviewed policy instance and are not inherited by a
future CPV-2022 policy automatically.

## Decisions required

1. **All renamed cross-survey concepts:** compare official source definitions, questionnaire universe/reference period, exact-release support and category domains; code resemblance is not equivalence.
2. **Category collapses:** `IV10→H11`, `II9→H13`, `II7→PROP`, `CH15→P05`, `CH09→P07`, and reverse recodes for `V01`, `H06`, `H09`, `H14`, `H13`, and `P07`. Decide whether each many-to-one loss is acceptable.
3. **Known semantic mismatches:** explicitly adjudicate at least `ESTADO↔CONDACT` age/reference-universe differences, `IV7↔H09` wording differences, `IV10↔H11` ternary-vs-binary structure, `II9↔H13` applicability/no-bathroom structure, `II1↔H16` room-count definitions, and `II7↔PROP` tenure category systems.
4. **Education/literacy:** compare `CH09/CH10/CH12/CH13` with raw Census `P07/P08/P09/P10`, including age universes and missing/ignored codes. Do not confuse raw fields with REDATAM aliases.
5. **IX_TOT:** decide whether the Census-side concept is derived from exact complete sample membership, checked against `TOTPERS`, rather than treated as a raw Census field.
6. **Conditional changes:** approve or reject activity overwrite for age below 14 and `CH13=0` based on `CH12`; establish source universes before any transformation is promoted.
7. **Sample membership:** review historical removal of household records having `IV1=9`; it is not inherited automatically by the new exact-release plane.
8. **Clipping/missingness:** review historical `IX_TOT` clipping, `H16` clipping, negative-age clipping, and unsupported-category-to-null behavior against the current source codebooks and observed supports.
9. **Geography:** geography-derived external predictors remain outside the first 23-concept plane; `AGLO_rk` and `Reg_rk` are forbidden external predictors. Do not invent a substitute during this review.
10. **Temporal admissibility:** semantic approval does not imply that a 2010 donor observation is appropriate as a 2024 welfare-period predictor. `encuestador-de-hogares` owns that later decision.

## Directionality and precedence gate

Forward and reverse mappings are separately governed entries. A reverse rule is
never generated by inverting a forward value map: this matters particularly for
the collapsed categories, where the original source category cannot be
recovered. Before any rule executes, the registry validates the composite key
`(direction, entity, source_vintage, source_variable, target_variable,
rule_priority)`. Equal-precedence conflicts fail, and multiple applicable rules
for one source require an explicit `composition` declaration.

The `rename_assurance` field distinguishes unverified renames from lexically
identical passthroughs whose conceptual equivalence is still unverified. No
rename is approved merely because its spelling or codes align.

No derived-variable mapping currently carries approval. Any future derived mapping or rule that changes sample membership must pass the same gate before release status can change from `pending`.
