# EPH ↔ Censo Aligner

Alineador bidireccional para expresar variables seleccionadas de la Encuesta Permanente de Hogares (EPH) y del Censo Nacional bajo un contrato común y reglas de recodificación explícitas.

> **Estado:** candidato a mantenimiento. El paquete, la CLI, los mappings y los tests fueron construidos y sincronizados en 2025; las fuentes, vintages y pruebas no fueron revalidados en un entorno limpio durante esta actualización del README.

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

## Uso mínimo

Desde Python:

```python
import pandas as pd
from aligner.eph_align import harmonize_hogar

raw = pd.read_csv("EPH.csv")
aligned = harmonize_hogar(raw)
aligned.to_csv("EPH_aligned.csv", index=False)
```

Desde CLI:

```bash
python -m aligner.cli \
  --source eph \
  --target censo \
  --input EPH.csv \
  --output aligned.csv
```

Antes de usarlo sobre datos nuevos, revisar los flags disponibles en `aligner/cli.py` y los mappings aplicables al vintage de entrada.

## Validación

El repositorio incluye tests para el CDM y ambos sentidos de transformación. Una revisión de mantenimiento debería ejecutar:

```bash
pytest
```

y además comprobar invariantes del dataset real: columnas esperadas, dominios, cobertura, duplicados y pérdidas introducidas por cada recodificación.

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
