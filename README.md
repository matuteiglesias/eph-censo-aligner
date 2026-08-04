# EPH ↔ Censo Aligner

Alineador bidireccional para expresar variables seleccionadas de la Encuesta Permanente de Hogares (EPH) y del Censo Nacional bajo un contrato común y reglas de recodificación explícitas.

> **Estado:** release de mapping v1, probado únicamente contra el vintage sintético `fixture-v1`. Ningún vintage real de EPH o Censo está soportado hasta completar revisión metodológica.

## Por qué existe

EPH y Censo describen personas y hogares con coberturas, preguntas y códigos diferentes. Este repositorio hace esas diferencias **visibles y ejecutables** mediante:

- renombre de columnas;
- crosswalks de valores;
- colapso de familias de variables;
- reglas condicionales;
- joins geográficos y excepciones documentadas;
- casteo y validaciones básicas.

El objetivo es producir tablas comparables para tareas posteriores, no afirmar que ambas fuentes sean estadística o conceptualmente equivalentes.

## Superficie principal

```text
aligner/
  cdm.py             contrato mínimo de datos
  eph_align.py       EPH → contrato tipo Censo
  censo_align.py     Censo → contrato tipo EPH
  cli.py             interfaz de línea de comando
  io.py              lectura de datos y mappings
  utils.py           transformaciones reutilizables
  validate.py        controles de integridad
  mappings/          columnas, valores y excepciones

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

La CLI real exige dirección, entidad, input, directorio de release y vintage:

```bash
python -m aligner.cli --direction eph-to-censo --entity hogar \
  --input fixtures/eph/hogar.csv --region fixtures/regions.csv \
  --source-vintage fixture-v1 --release-id fixture-v1 --output-dir out/release
```

Cada directorio contiene `aligned.csv`, `variable-report.json`, `loss-report.json`,
`compatibility.json` y `manifest.json`. El manifest usa el envelope compartido
`research-artifact-manifest/v1`; declara productor, commit/estado del worktree,
vintage, método, inputs, archivos con tamaño y SHA-256, informes y limitaciones.
Las filas se ordenan por identificadores disponibles; los identificadores se
preservan y encabezan un orden de columnas estable. JSON usa claves ordenadas y
CSV usa LF y vacío para null.

Las reglas de ida y vuelta son entradas independientes: el sistema nunca invierte
automáticamente un colapso o condicional. Antes de ejecutar valida prioridad,
unicidad y composición explícita. El informe de pérdida reconcilia toda fila de
entrada en una sola disposición terminal (`emitted`, `removed`, `invalid`,
`unsupported`, `unmatched` o `failed`).

## Vintages y revisión

El registro máquina-legible es `aligner/mappings/registry.json`. Sólo `fixture-v1` está soportado en ambas direcciones; todos los vintages reales son desconocidos/no soportados. Los colapsos, condicionales, cambios de muestra y overrides geográficos siguen `pending`; consultar `docs/MAPPING_REVIEW_REQUIRED.md`. Esto es una traducción inspeccionable, no una declaración de equivalencia estadística.

## Integración opcional por artefacto

Este repositorio **no** forma parte obligatoria de cada corrida de modelos. Un
consumidor usa una copia inmutable del directorio de release sólo cuando necesita
armonización EPH/Censo; no ejecuta este repositorio ni lee un checkout hermano.
Puede validar el artefacto antes del preprocessing, sin cargar pandas:

```bash
python -m aligner.integration path/to/release/manifest.json \
  --mode synthetic --expected-vintage fixture-v1 \
  --geography-identifier-contract research.argentina-dpto/v1
```

La declaración `compatibility.json` publica el contrato de artefacto
`research.eph-census-crosswalk/v1`, el contrato consumidor y la política que
rechaza crosswalks sintéticos en corridas reales o releases pendientes en modo
aprobado. La fixture que prueba crosswalk opcional, procedencia anual y la
composición con releases de fuente/geografía corresponde al repositorio consumidor
`income-modeling-eph`; no se crea aquí una dependencia runtime distribuida.

## Autoridad y límites

Este repositorio posee:

- el contrato mínimo utilizado por el alineador;
- los mappings versionados;
- las reglas de transformación y validación.

No posee:

- la definición oficial de las variables de EPH o Censo;
- los microdatos fuente;
- una garantía de equivalencia entre conceptos;
- la metodología de inferencia de un producto downstream.

Cada output debería conservar el vintage de las fuentes y la versión de los mappings utilizados.

## Próxima revisión útil

1. fijar dependencias e instalación reproducible;
2. asociar cada mapping con un vintage de EPH/Censo;
3. agregar fixtures pequeños representativos;
4. documentar pérdidas o ambigüedades por variable;
5. conectar el output con un consumidor real antes de ampliar el alcance.

El nombre actual describe bien el producto; no se recomienda renombrarlo.
