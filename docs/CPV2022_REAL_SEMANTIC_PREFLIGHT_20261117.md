# CPV-2022 real-sample semantic preflight (issue #26)

**Scientific status: bounded commissioning evidence. Not a qualified EPH→CPV-2022
transport feature plane, and no permission to score household income.**

## Inputs and source provenance

- Source: `research.census-target-year-sample/v2` release
  `census-sample-2024-9b0a450e6a296d46` on Elements1 under
  `CENSO_work/benchmarks/rpo11-cpv2022-sampler-qualification-20261117/scale-3000/releases/`.
- Frame: `arg-cpv2022-frame-399976ee798812af`, created from the first 3,000
  *ID-sorted* RPO-11 RADIOs, of which 2,996 were committed and four were
  `NEEDS_LOCAL`. This does **not** represent a complete department or a
  representative national frame.
- Diagnostic sample: **1,082 households, 2,392 persons, 13 departments**.
  Synthetic 2024 target masses **equal the observed donor masses**, not official
  population projections. `commissioning_only=true`,
  `publication_allowed=false`.
- Source definitions:
  - [INDEC CPV-2022 Redatam database definitions](https://redatam.indec.gob.ar/redarg/CENSOS/CPV2022/Docs/Redatam_Definiciones_de_la_base_de_datos.pdf)
  - [INDEC CPV-2022 household dictionary](https://redatam.indec.gob.ar/binarg/RpWebStats.exe/Dictionary?BASE=CPV2022&ITEM=DICHOG&lang=ESP)
  - [INDEC CPV-2022 person dictionary](https://redatam.indec.gob.ar/binarg/RpWebStats.exe/Dictionary?BASE=CPV2022&ITEM=DICPOB&lang=ESP)
  - [INDEC EPH 2024-Q2 record design](https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_registro_2T2024.pdf); the actual 2024-Q3 source release and document must be bound before EPH-specific semantic approval.

## Discovered *semantic collisions* (not missing-data failures)

| Historical concept (CPV-2010 policy) | CPV-2022 source | State |
| --- | --- | --- |
| `P02`: EPH `CH04` sex binary | `P02`: sex registered at birth, 1=female, 2=male | **Raw diagnostic proxy only**. Value reversal `1→2, 2→1`; questionnaire meanings differ. |
| `P03`: EPH `CH06` age | `EDAD`, age on census date (18 May 2022); **2022 `P03` is gender identity** | **Source-age diagnostic**. Temporal transport to 2024 is not approved. |
| `IX_TOT`: household size | Complete `person_membership` per `frame_household_id` | **Exact donor-membership diagnostic**. EPH household universe comparison still needed. |
| `H05`: floors | `H10`: floors | Candidate with changed field ID and potentially recoded floor categories. |
| `H06` / `H07`: roof / ceiling | April 2025 VP `H11` (label: exterior roof material), not online `H11_H12` | Requires a source-vintage-specific review; do not infer ceiling presence. |
| `H08`: water availability | `H13`: water availability | Candidate, 2022 source universe/value support review required. |
| `H09`: water provenance | `H14`: water provenance | Candidate with changed field ID / category definitions. |
| `H10`: bathroom presence | April VP `H15_17` and `H16` (online `H15_H17`) | 2022 `H10` is **floor material**; direct name reuse is wrong. |
| `H12`: toilet sewer destination | `H18`: toilet discharge | Candidate requiring response universe review. |
| `H13`: bathroom sharing | None established in VP | **Unsupported until independent evidence.** 2022 `H13` is water. |
| `H14`: cooking fuel | `H19`: cooking fuel | 2022 `H14` is **drinking/cooking water source**. |
| `H15`: bedrooms | None established in VP | **Unsupported**: 2022 `H20` is total rooms, not sleeping rooms. The official VP definitions do not document `H21`. |
| `H16`: total rooms | `H20`: total rooms | 2022 `H16` is **number of bathrooms**. |
| `PROP`: dwelling/land tenure | `H22` dwelling ownership, `H23` documentation | Not a one-to-one tenure concept; needs reviewed collapse. |
| 2010 `P07/P08/P09/P10`: education variables | 2022 `P06/P07/P08/P09/P10/P11/CONASI` | Same codes refer to different questions. Need universe-aware derivation and 2024 EPH categories. |
| 2010 `P05`: birthplace | 2022 `P13` / `P15` | Potential country-group recode, not approved. |
| `CONDACT` | 2022 `CONDACT` | Matching field name is insufficient: age universe and time-period mismatch. |
| `V01` | 2022 `V01` | Matching name; category coding/universe review remains open. |

### Critical discovery: online dictionary and extracted source are distinct vintages

The archive used for the first 3,000 RADIOs is an **April 2025 RedatamX VP**
source. We directly queried its HOGAR catalog using
`redatamx::redatam_variables()`. The catalog contains `H11`,
`H15_17`, `H15_17_18`, `H20CP` where the currently served
online INDEC dictionary lists `H11_H12`, `H15_H17`,
`H15_H17_H18`, `H20_HACINA`. The missing online spellings
are **not extraction losses**: our all-stored profile extracted the April
VP names and the 2022 Parquet sample shows their nonempty observed values.

**Important:** name matching between these two 2022 source vintages is
not enough to establish equal code meanings. For example April VP `H11`
is labeled exterior roof material, whereas current online
`H11_H12` explicitly mentions interior roof covering too. The
sample contains `H11=99` under a zero missing-mask, so sentinel
values must be interpreted with source-specific coding rather than
simply assuming mask=0 means an ordinary valid category.

The full **source-only** (no records) 13 vivienda / 30 hogar /
34 persona variable inventory is saved on Elements:
`CENSO_work/benchmarks/rpo11-cpv2022-aligner-qualification-20261117/cpv2022_vp_source_catalog_apr2025.json`.
Its SHA-256 is `4edf26934c0145638edab661706605f15d9eb02a0439162f7501ff4470588f30`.
This finding does **not** require rerunning our validated extracts.

The complete set of **23** decisions, including the historical EPH field and the
2022 candidate source(s), is machine-readable in
`aligner/codebooks/real_2024q3_cpv2022_candidate_review_v1.json`.
Only 3 simple *source-side diagnostics* are currently materialized:
`donor_household_size`, `age_on_2022_05_18`, and
`sex_birth_eph_binary_proxy`. **None** is `transport_approved`.

## Reproduction and isolation

```bash
ROOT=/media/matias/Elements1/CENSO_work/benchmarks/rpo11-cpv2022-sampler-qualification-20261117/scale-3000/releases/census-sample-2024-9b0a450e6a296d46
OUT=/media/matias/Elements1/CENSO_work/benchmarks/rpo11-cpv2022-aligner-qualification-20261117
python3 -m aligner.cpv2022_preflight --census-sample-root "$ROOT" --output-root "$OUT"
```

The command checks the sample v2 contract, exact file SHA-256s, positive
household completeness, explicit 2022 vintage, explicit partial-coverage and
non-publishable commissioning labels, raw source masks, age and binary-category
support, and exact person/household membership. It emits an **immutable**
manifest-hashed local Parquet diagnostic release, a QA report, and **aggregated
source code/mask frequencies** for candidate 2022 variables; no raw Census rows
are committed to Git or published.

**The CPV-2010 alignment is unchanged**: its existing codebooks and executable
feature-plane code continue to reject any 2022 sample. No fall-through to the
historical 2010 recodes is allowed.

## Next exact work (issue #26 remains open)

1. Obtain/locate the exact `eph-2024-q3-3b6a7a15c4af` producer release and
   bind its microdata schema, questionnaire design and code distributions. The
   2024-Q2 document is evidence of coding direction, not a replacement for
   exact-quarter evidence.
2. Select the **minimal actually deployable predictor set** requested by the
   current Encuestador, and approve or reject each EPH×CPV-2022 mapping with
   questionnaire, code, universe and mask evidence. Do not force all 23 old
   concepts into a revived model.
3. Assess all observed 2022 source categories and missing masks from the
   preflight QA. Where a concept is not in the VP source, identify an official
   derivation, or mark it unsupported. Do not change the national extractor
   merely because a CPV-2010 field name is absent.
4. Test *bidirectional comparable* EPH and Census features on their exact
   releases; quantify domain support and missingness. Authorize a production
   semantic plane only with resolved temporal role and statistical transport
   judgment. **No poverty/Encuestador inference as part of this issue yet.**
