# EPH ↔ Censo Aligner

Alineador semántico bidireccional para expresar variables seleccionadas de la Encuesta Permanente de Hogares (EPH) y del Censo bajo contratos comunes y reglas de recodificación explícitas.

> **Estado:** el contrato sintético v1 sigue disponible; la revisión real EPH 2024-Q3 ↔ CPV-2010 está materializada; el handoff donor-labor CPV-2010 está comisionado; y el plano longitudinal canónico EPH 2017-Q1..2026-Q1 ya fue materializado bajo perfiles gobernados. El compilador real sigue siendo policy-driven y donor-vintage-neutral. Una política CPV-2022 real todavía requiere su propia revisión semántica.

## Qué problema resuelve

EPH y Censo describen personas y hogares con coberturas, preguntas, universos y códigos diferentes. Este repositorio vuelve esas diferencias **visibles, versionadas y ejecutables** mediante renombres, recodificaciones de valores, colapsos de familias de variables, reglas condicionales, validaciones y excepciones documentadas.

La salida es una **alineación semántica inspeccionable**. No implica equivalencia estadística, intercambiabilidad de fuentes ni validez de un modelo entrenado en una fuente para inferir sobre la otra.

### Alineación semántica no es crosswalk geográfico

En documentación nueva usamos *alineación semántica EPH↔Censo* para este producto. El identificador histórico `research.eph-census-crosswalk/v1` se conserva por compatibilidad de artefactos, pero no debe interpretarse como un crosswalk territorial ni como asignación de una geografía a otra. Las relaciones geográficas son otra clase de problema y otra autoridad.

## Superficie principal

```text
aligner/
  cdm.py             contrato mínimo de datos
  eph_align.py       EPH → contrato común
  censo_align.py     Censo → contrato común
  cli.py             interfaz de línea de comando
  io.py              lectura de datos y mappings
  utils.py           transformaciones reutilizables
  validate.py        controles de integridad
  mappings/          columnas, valores y excepciones
  codebooks/         evidencia y políticas de revisión real versionadas

docs/DEPLOYMENT_FEATURE_PLANE.md
                     vocabulario para auditar qué variables podrían formar
                     una futura superficie model-facing desplegable
tests/               pruebas unitarias
notas.md              decisiones metodológicas
```

## Instalación y comandos

```bash
make install
make check
make test
make smoke
make release-fixture
```

Ejemplo sintético:

```bash
python -m aligner.cli --direction eph-to-censo --entity hogar \
  --input fixtures/eph/hogar.csv --region fixtures/regions.csv \
  --source-vintage fixture-v1 --release-id fixture-v1 --output-dir out/release
```

Cada directorio contiene `aligned.csv`, `variable-report.json`, `loss-report.json`, `compatibility.json` y `manifest.json`. El manifest usa `research-artifact-manifest/v1` y fija productor, commit/estado del worktree, vintage, método, inputs, archivos, SHA-256, informes y limitaciones.

Las reglas de ida y vuelta son independientes: el sistema nunca invierte automáticamente un colapso o condicional. El informe de pérdida reconcilia toda fila de entrada en una disposición terminal (`emitted`, `removed`, `invalid`, `unsupported`, `unmatched` o `failed`).

## Vintages y revisión

El registro histórico/bidireccional sigue en `aligner/mappings/registry.json`. Para datos reales, la unidad de autoridad es una **review policy exacta** que fija por separado:

- release EPH y período EPH;
- frame/sample Census exactos;
- `census_vintage` (2010 o 2022);
- período objetivo del muestreo;
- evidencia de codebook;
- decisión semántica y rol temporal de cada concepto.

La política real actualmente materializada es EPH 2024-Q3 ↔ CPV-2010. El compilador no contiene una rama científica especial para 2010: una futura política CPV-2022 usa el mismo código y contrato, pero debe aportar su propia evidencia y adjudicación.

Ejemplo:

```bash
semantic-plane materialize-real \
  --policy aligner/codebooks/real_2024q3_cpv2010_review_policy.json \
  --eph-release-root /path/to/eph-release \
  --census-sample-root /path/to/census-sample \
  --output-dir /path/to/semantic-plane
```

Ver `docs/MAPPING_REVIEW_REQUIRED.md`.

## Plano longitudinal canónico de composición (C5)

El contrato `research.eph-longitudinal-composition-plane/v1` consume una release C2 exacta
(`research.eph-longitudinal-analysis-frame/v1`) y preserva su identidad de fila sin
reconstruir paneles ni recodificar dentro de `encuestador-de-hogares`.

Los perfiles versionados son:

- `P0_LONG`: baseline histórico mínimo; reutiliza conceptos canónicos aprobados donde
  existen y conserva `CH07` como concepto EPH-only gobernado. No se inventa un análogo
  Census para CH07.
- `P1R_NOLAB_LONG`: la superficie P1-R aprobada menos `CONDACT`; `H06`, `H11` y
  `H16` permanecen excluidos por estar `needs-judgment`.

El compilador reutiliza las transformaciones del policy exacto EPH-2024-Q3/CPV-2010 y
audita soporte `period × concept`. La gate real L3B ya fue ejecutada sobre los 37
trimestres. Los códigos históricos reconocidos como estados especiales/no sustantivos
se gobiernan en `aligner/codebooks/longitudinal_specials_v1.json` y se convierten en
null **sólo para esa feature**, preservando la fila C2. Códigos desconocidos o drift
semántico sustantivo continúan fallando cerrado.

```bash
semantic-plane profiles
semantic-plane materialize-longitudinal \
  --c2-release-root /path/to/c2-release \
  --profile P1R_NOLAB_LONG \
  --output-root /path/to/c5-releases
```

Materializaciones reales actuales:

- `P0_LONG`: `eph-longitudinal-composition-p0_long-7b8fdc0ec1f2a553`;
- `P1R_NOLAB_LONG`: `eph-longitudinal-composition-p1r_nolab_long-ed30aa112c9b7d31`.

Ambas preservan exactamente las 1,869,620 filas C2 en 37/37 períodos, excluyen estado laboral individual corriente y terminan con cero códigos inesperados/imposibles sin resolver.

El mismo registro puede proyectar `P1R_NOLAB_LONG` sobre columnas Census ya compiladas
por el semantic compiler CPV-2010; ese hook selecciona features, no vuelve a recodificar.
`P0_LONG` falla cerrado del lado Census mientras CH07 no tenga una decisión cross-survey.

Ver `docs/LONGITUDINAL_COMPOSITION_PLANE.md` y el handoff local L3B.

## Estado laboral del donante: reloj explícito

La política real CPV-2010 ahora publica un handoff Census-only separado:

```text
census_donor_labor_state.parquet
  row_id / household_id
  sample_person_id / sample_household_id
  frame_person_id / frame_household_id / frame_dwelling_id
  donor_condact
  donor_condact_vintage
  donor_condact_semantic_status
```

Para CPV-2010, `donor_condact_vintage=2010`. La materialización real L3A vigente es `eph-cpv2010-semantic-plane-2024q3-v2` con 469,172 personas, identidad preservada y ninguna autorización de transporte estadístico. El valor proviene del `CONDACT`
censal revisado y recodificado bajo la misma política semántica; no se relabela
como estado laboral corriente del período EPH o del período de bienestar.

El `CONDACT` del plano P1-R se conserva por compatibilidad del contrato v1,
pero el manifest marca explícitamente que su lado Census es una observación de
vintage donante. Un consumidor que estudie persistencia temporal debe usar el
handoff `donor_condact*` y construir su análogo de entrenamiento fuera de este
repositorio con evidencia EPH repetida. Este repositorio no crea
`donor_condact` en EPH copiando `ESTADO`/CONDACT corriente.

`donor_labor_qa.json` registra soporte bruto/canónico, categorías especiales a
null, universo de edad, faltantes, preservación exacta de identidad y separación
de relojes. La misma representación acepta un futuro CPV-2022 mediante otra
review policy source-backed; no requiere una rama de compilador específica.

## Integración por artefacto

Un consumidor usa una copia inmutable de una release cuando necesita alineación semántica; no necesita ejecutar este repositorio ni leer un checkout hermano. Puede validar el artefacto antes del preprocessing:

```bash
python -m aligner.integration path/to/release/manifest.json \
  --mode synthetic --expected-vintage fixture-v1 \
  --geography-identifier-contract research.argentina-dpto/v1
```

`compatibility.json` conserva por compatibilidad el tipo de artefacto `research.eph-census-crosswalk/v1`. Esa etiqueta histórica no amplía el alcance científico del producto.

## Autoridad y límites

Este repositorio posee las reglas versionadas de correspondencia semántica, sus validaciones, reportes de pérdida/ambigüedad y releases de alineación.

No posee la definición oficial de las variables fuente, los microdatos, geografía argentina, modelos de ingreso, ejecución de inferencia sobre muestras Census ni una garantía de transporte estadístico entre EPH y Censo.

## Próximo trabajo sustantivo

El siguiente handoff real es revisar CPV-2022 contra el período EPH objetivo usando el mismo compilador y los mismos conceptos canónicos cuando la equivalencia esté justificada. La alineación semántica no decide transporte estadístico: soporte, domain shift y admisibilidad temporal final pertenecen a `encuestador-de-hogares`.
