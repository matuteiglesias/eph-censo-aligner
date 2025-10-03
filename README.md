# EPH–Censo Aligner

Este proyecto contiene un **alineador bidireccional** entre microdatos de la **Encuesta Permanente de Hogares (EPH)** y el **Censo Nacional**. Su objetivo es permitir que tablas de ambas fuentes se comparen o se integren bajo un marco común, aplicando reglas de recodificación, validación y enriquecimiento.

---

## Estructura principal

* `aligner/`

  * **`eph_align.py`**: transforma respuestas de EPH para que imiten los códigos del Censo.
  * **`censo_align.py`**: el complemento: adapta respuestas del Censo para que se parezcan a los códigos de EPH.
  * **`utils.py`**: utilidades modulares (rename, collapse, recode, clip, filters, join, overrides, validate, cast).
  * **`cdm.py`**: contrato mínimo de datos (estructura CDM) para armonización consistente.
  * **`cli.py`**: interfaz de línea de comando para ejecutar los alineadores con flags de validación o enriquecimiento.
  * **`io.py`**: helpers de entrada/salida para leer datasets y mappings.
  * **`validate.py`**: validadores básicos de integridad.
  * **`mappings/`**

    * `censo/columns.yaml`, `censo/values.yaml`: crosswalk y recodificaciones propias del Censo.
    * `eph/columns.yaml`, `eph/values.yaml`: equivalentes para la EPH.
* `tests/`: pruebas unitarias que cubren los módulos principales.
* `notas.md`: apuntes y decisiones metodológicas.

---

## Cómo usar

1. **Instalar dependencias** (mínimas: `pandas`, `numpy`).
2. Preparar un `DataFrame` de EPH o Censo.
3. Importar y correr el pipeline:

```python
import pandas as pd
from aligner.eph_align import harmonize_hogar, harmonize_individual

df_eph = pd.read_csv("EPH.csv")
df_hogar_aligned = harmonize_hogar(df_eph)
```

4. O bien, desde CLI:

```bash
python -m aligner.cli --source eph --target censo --input EPH.csv --output aligned.csv
```

---

## Qué hace el alineador

* **Rename**: cruza nombres de columnas (EPH ↔ Censo).
* **Families collapse**: colapsa variables multicolumna tipo `V*_01, V*_02`.
* **Recode**: aplica mapas de valores específicos (ej. `IV10`, `II7`, `II9`).
* **Clip & filter**: corrige valores fuera de rango y aplica filtros de calidad.
* **Conditional set**: reglas contextuales (ej. menores de 14 → `CONDACT=0`).
* **Join + overrides**: agrega región por departamento con excepciones documentadas.
* **Validate**: chequea presencia de columnas clave y consistencia.
* **Types**: asegura que columnas monetarias y numéricas estén casteadas.
