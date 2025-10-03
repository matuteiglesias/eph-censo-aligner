# censo_align.py
from __future__ import annotations
from typing import Optional
import pandas as pd

# Reutilizamos utilidades existentes
from utils import (
    rename_columns, collapse_family_multi_any,
    apply_recode, clip_columns, join_region_by_dpto, apply_overrides,
    validate_required, conditional_set, cast_numeric
)

# ------------------------------------------------------
# 1) Crosswalk (subset Censo → EPH) y columnas monetarias
#    (reverse del de EPH → Censo)
# ------------------------------------------------------

NAMES_CENSO = [
    'IX_TOT','P02','P03','CONDACT','AGLOMERADO',
    'V01','H05','H06','H07','H08','H09','H10','H11','H12','H16','H15','PROP','H14','H13',
    'P07','P08','P09','P10','P05'
]

NAMES_EPH = [
    'IX_TOT','CH04','CH06','CONDACT','AGLOMERADO',
    'IV1','IV3','IV4','IV5','IV6','IV7','IV8','IV10','IV11','II1','II2','II7','II8','II9',
    'CH09','CH10','CH12','CH13','CH15'
]

# Reverse crosswalk: Censo → EPH
CROSSWALK_CENSO_TO_EPH = dict(zip(NAMES_CENSO, NAMES_EPH))

# Monetarias que nos interesa tipar si existen
COL_MON = ['P21', 'P47T', 'PP08D1', 'TOT_P12', 'T_VI', 'V12_M', 'V2_M', 'V3_M', 'V5_M']

# ------------------------------------------------------
# 2) Reglas para hacer que Censo “mimique” a EPH
#    (aplicar ANTES del rename para que maten los nombres Censo)
# ------------------------------------------------------

RECODE_CENSO_TO_EPH = {
    # V01 (Censo) → IV1 (EPH)
    'V01': {'map': {1:1, 2:6, 3:6, 4:2, 5:3, 6:4, 7:5, 8:6}},
    # H06 (Censo) → IV4 (EPH)
    'H06': {'map': {1:1, 2:2, 3:3, 4:4, 5:5, 6:6, 7:7, 8:9}},
    # H09 (Censo) → IV7 (EPH)
    'H09': {'map': {1:1, 2:2, 3:3, 4:4, 5:4, 6:4}},
    # H14 (Censo) → II8 (EPH)
    'H14': {'map': {1:1, 2:4, 3:2, 4:2, 5:4, 6:3, 7:4, 8:9}},
    # H13 (Censo) → II9 (EPH)
    'H13': {'map': {1:1, 2:2, 4:0}},
    # P07 (Censo) → CH09 (EPH)
    'P07': {'map': {1:1, 2:2, 0:2}},
    # Tip: si necesitás más, agregalos acá con el mismo patrón
}

# Clips sobre nombres Censo (antes del rename)
CLIP_CENSO = {
    # H16 (Censo) → II1 (EPH); pediste clip [0,9]
    'H16': {'min': 0, 'max': 9},
}

# ------------------------------------------------------
# 3) Orquestadores: Censo → EPH
# ------------------------------------------------------

def censo_to_eph_hogar(
    df: pd.DataFrame,
    region_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Alinea un DataFrame de Censo (hogares/personas mezcladas o sólo hogar)
    al subset EPH esperado para HOGAR.

    Pasos:
      1) recode/clip en nombres Censo
      2) rename (Censo → EPH) sobre el subset
      3) families.collapse (si vienen splits tipo V*_NN inesperados)
      4) (opcional) join de Region por DPTO + overrides
      5) types (monetarias)
      6) validate (requeridos EPH de tu subset)
    """
    out = df.copy()

    # 1) Normalizar respuestas de Censo a marcos EPH
    out = apply_recode(out, RECODE_CENSO_TO_EPH)
    out = clip_columns(out, CLIP_CENSO)

    # 2) Renombrar subset Censo → EPH
    out = rename_columns(out, CROSSWALK_CENSO_TO_EPH)


    # 4) Región por DPTO + overrides
    if region_df is not None:
        out = join_region_by_dpto(out, region_df, on="DPTO", take="Region", into="Region")
        out = apply_overrides(out, [
            ({"AGLOMERADO": 33, "Region": "Pampeana"}, {"Region": "Gran Buenos Aires"}),
            ({"AGLOMERADO": 93, "Region": "Pampeana"}, {"Region": "Patagónica"}),
        ])

    # 5) Types (si alguna monetaria viniera en estas tablas)
    out = cast_numeric(out, COL_MON)

    # 6) Validación mínima para el subset hogar en *nombres EPH*
    validate_required(out, ['IX_TOT', 'CH04', 'CH06', 'CONDACT', 'AGLOMERADO'], where="censo→eph_hogar")

    return out


def censo_to_eph_individual(
    df: pd.DataFrame,
    region_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Alinea un DataFrame de Censo al subset EPH esperado para INDIVIDUAL.

    Pasos:
      1) recode/clip en nombres Censo
      2) rename (Censo → EPH)
      3) families.collapse para _NN_M si existieran en insumos modernos
      4) reglas de limpieza/condición (si querés replicar tu lógica mínima)
      5) join de Region por DPTO + overrides
      6) types (monetarias)
      7) validate (requeridos EPH del subset)
    """
    out = df.copy()

    # 1) Normalización Censo → marcos EPH
    out = apply_recode(out, RECODE_CENSO_TO_EPH)
    out = clip_columns(out, CLIP_CENSO)

    # 2) Rename al naming EPH
    out = rename_columns(out, CROSSWALK_CENSO_TO_EPH)

    # 3) Families collapse (defensivo)
    for base in ["V2", "V5", "V11", "V21", "V22"]:
        out = collapse_family_multi_any(out, f"{base}", f"{base}_M")

    # 4) Reglas de limpieza/condición mínimas (opcionales, espejo de tu aligner)
    #    Ejemplo: menores de 14 → CONDACT=0 si existe CH06
    if 'CH06' in out.columns:
        out = conditional_set(out, ('CH06', '<', 14), {'CONDACT': 0})

    # 5) Región por DPTO + overrides
    if region_df is not None and 'DPTO' in out.columns:
        out = join_region_by_dpto(out, region_df, on="DPTO", take="Region", into="Region")
        out = apply_overrides(out, [
            ({"AGLOMERADO": 33, "Region": "Pampeana"}, {"Region": "Gran Buenos Aires"}),
            ({"AGLOMERADO": 93, "Region": "Pampeana"}, {"Region": "Patagónica"}),
        ])

    # 6) Tipado monetario
    out = cast_numeric(out, COL_MON)

    # 7) Validación mínima para el subset individual en *nombres EPH*
    validate_required(out, ['CH04', 'CH06', 'CONDACT', 'AGLOMERADO'], where="censo→eph_individual")

    return out
