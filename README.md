# EPH ↔ Censo Aligner

Alineador semántico bidireccional para expresar variables seleccionadas de la Encuesta Permanente de Hogares (EPH) y del Censo bajo contratos comunes y reglas de recodificación explícitas.

> **Estado:** el contrato sintético v1 sigue disponible; además existe una revisión real acotada y source-backed para EPH 2024-Q3 ↔ CPV-2010. El compilador real es policy-driven y donor-vintage-neutral: CPV-2010 y CPV-2022 son instancias revisadas del mismo contrato, no pipelines separados. Una política CPV-2022 real todavía requiere su propia revisión semántica.

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
