

# Guía de cambios por época

## HOGAR

### Canon

* Hay un **core estable (83 columnas)**. 

`
CODUSU, ANO4, TRIMESTRE, NRO_HOGAR, REALIZADA, REGION, MAS_500, AGLOMERADO, PONDERA, IV1, IV1_ESP, IV2, IV3, IV3_ESP, IV4, IV5, IV6, IV7, IV7_ESP, IV8, IV9, IV10, IV11, IV12_1, IV12_2, IV12_3, II1, II2, II3, II3_1, II4_1, II4_2, II4_3, II5, II5_1, II6, II6_1, II7, II7_ESP, II8, II8_ESP, II9, V1, V2, V3, V4, V6, V7, V8, V9, V10, V12, V13, V14, V15, V16, V17, V18, V19_A, V19_B, IX_TOT, IX_MEN10, IX_MAYEQ10, ITF, DECIFR, IDECIFR, RDECIFR, GDECIFR, PDECIFR, ADECIFR, IPCF, DECCFR, IDECCFR, RDECCFR, GDECCFR, PDECCFR, ADECCFR, VII1_1, VII1_2, VII2_1, VII2_2, VII2_3, VII2_4
`


Todo lo demás se interpreta relativo a ese core.

### Era A - 2003 Q3 a 2024 Q3

* **Extras que pueden aparecer**: `V5`, `V11`, `V21`, `V22`. 
* **Alias de peso del hogar**:
  * **2003 Q3 a 2011 Q4**: `IDIMPH` (predomina en `Hog_*`) 
  * **desde 2012 Q1**: `PONDIH` (predomina en `usu_hogar_*`)


### Era B — desde 2024 Q4 (rediseño con expansión)

* **Estructura:** igual a Era A.
* **Aparecen versiones “spliteadas”** (one-hot/slots):

  * `V2_01`, `V2_02`, `V2_03`
  * `V5_01`, `V5_02`, `V5_03`
  * `V11_01`, `V11_02`
  * `V21_01`, `V21_02`, `V21_03`
  * `V22_01`, `V22_02`, `V22_03`
* **Peso**: `PONDIH`.


#### Observaciones prácticas HOGAR

* Donde existan versiones `_NN`, conviene:

  * **Colapsar** (p.ej. `V21 = argmax(V21_01..03)` o lista de códigos activos), o
  * **Normalizar a largo**: `(variable, código, valor)`.


---

## INDIVIDUAL

### Canon

* El **core** de variables compartidas a lo largo de la series es: 


`
CODUSU, ANO4, TRIMESTRE, NRO_HOGAR, COMPONENTE, H15, REGION, MAS_500, AGLOMERADO, PONDERA, CH03, CH04, CH06, CH07, CH08, CH09, CH10, CH11, CH12, CH13, CH14, CH15, CH16, NIVEL_ED, ESTADO, CAT_OCUP, CAT_INAC, PP02C1, PP02C2, PP02C3, PP02C4, PP02C5, PP02C6, PP02C7, PP02C8, PP02E, PP02H, PP02I, PP03C, PP03D, PP3E_TOT, PP3F_TOT, PP03G, PP03H, PP03I, PP03J, INTENSI, PP04A, PP04B_COD, PP04B1, PP04B2, PP04B3_MES, PP04B3_ANO, PP04B3_DIA, PP04C, PP04D_COD, PP04G, PP05B2_MES, PP05B2_ANO, PP05B2_DIA, PP05C_1, PP05C_2, PP05C_3, PP05E, PP05F, PP05H, PP06A, PP06C, PP06D, PP06E, PP06H, PP07A, PP07C, PP07D, PP07E, PP07F1, PP07F2, PP07F3, PP07F4, PP07F5, PP07G1, PP07G2, PP07G3, PP07G4, PP07G_59, PP07H, PP07I, PP07J, PP07K, PP08D1, PP08D4, PP08F1, PP08F2, PP08J1, PP08J2, PP08J3, PP09A, PP09B, PP09C, PP10A, PP10C, PP10D, PP10E, PP11A, PP11B_COD, PP11B1, PP11B2_MES, PP11B2_ANO, PP11B2_DIA, PP11C, PP11C99, PP11D_COD, PP11G_ANO, PP11G_MES, PP11G_DIA, PP11L, PP11L1, PP11M, PP11N, PP11O, PP11P, PP11Q, PP11R, PP11S, PP11T, P21, DECOCUR, IDECOCUR, RDECOCUR, GDECOCUR, PDECOCUR, ADECOCUR, TOT_P12, P47T, DECINDR, IDECINDR, RDECINDR, GDECINDR, PDECINDR, ADECINDR, V3_M, V4_M, V8_M, V9_M, V10_M, V12_M, V18_M, V19_AM, T_VI, ITF, DECIFR, IDECIFR, RDECIFR, GDECIFR, PDECIFR, ADECIFR, IPCF, DECCFR, IDECCFR, RDECCFR, GDECCFR, PDECCFR, ADECCFR
`


Los cambios abajo son respecto a ese core.

### Era 1 - 2003 Q3 a 2010 Q4

* **Presentes (extras)**:

  * `CH05`, `IMPUTA`
  * `CH15_COD`, `CH16_COD`
  * `PP04C99`
  * `PP09A_ESP`, `PP09C_ESP`
  * Pesos: `IDIMPP`.
  * Flags módulo (no spliteados): `V2_M`, `V5_M`, `V11_M`, `V21_M`
* **Notas**:

  * Múltiples pesos además de `PONDERA`.
  * Coexisten familias **COD/ESP**; `PP04C99` está disponible.

### Era 2 — 2011 (año especial)

* **Presentes**: `PP04B_CAES`, `PP11B_CAES`, `IDIMPP`, `V2_M`, `V5_M`, `V11_M`, `V21_M`
* **Ausentes**: `PP04C99`, `PP09A_ESP`, `PP09C_ESP`
* **Notas**:

  * Se usan variables **_CAES** en PP04B/PP11B.
  * Se mantiene un peso/índice `IDIMPP`.
  * Las variables `*_ESP` de PP09 **no** están ese año.

### Era 3 — 2012–2015 (clásica estable)

* **Estructura**: alinea con el core típico (sin splits `_NN`).
* **CAES/COD/ESP**: patrón consistente con el core (PP04C99 vuelve a estar).

### Era 4 — 2016 - 2024 Q3

* **Contrato post-2016** (de aquí en adelante hasta 2024 Q3):

* **Estructura**: sigue el core.
  * Prefiere `*_COD` donde existen; `*_ESP` como textos opcionales.
  * Campos de fechas desglosadas tipo `PP05B2_*`, `PP11B2_*`, `PP11G_*`.

* **Disponibilidad**:
  * `PP04C99` y `PP09A_ESP` presentes.
  * `PP09C_ESP` **suele estar**.

### Era 5 — desde 2024 Q4 (expansión amplia)

* **Siguen presentes** (extras): `CH05`, `IMPUTA`, `CH15_COD`, `CH16_COD`, `PP04C99`, `PP09A_ESP`
* **Ausente**: `PP09C_ESP` (vuelve a desaparecer en esta era)
* **Pesos**: además de `PONDERA`, aparecen `PONDIIO`, `PONDII`, `PONDIH`.
* **Splits de flags de módulo** (aparecen variantes `_NN_M`):

  * `V2_01_M`, `V2_02_M`, `V2_03_M`
  * `V5_01_M`, `V5_02_M`, `V5_03_M`
  * `V11_01_M`, `V11_02_M`
  * `V21_01_M`, `V21_02_M`, `V21_03_M`
  * `V22_01_M`, `V22_02_M`, `V22_03_M` (nuevo en esta era)
* **Nuevos campos de mercado laboral/episodios**:

  * `PP07B1_01`, `EMPLEO`, `SECTOR`
  * `PP02A`, `PP02B`, `PP02D`, `PP02F`, `PP02G`
  * `PP03K`, `PP04A1`
  * `PP05B3`, `PP05I`, `PP05J`, `PP05K`
  * `PP06E1`, `PP06K`, `PP06K_SEM`, `PP06K_MES`, `PP06L`
  * `PP07F1_1`, `PP07F1_2`, `PP07F1_3`, `PP07I2`, `PP07I3`, `PP07I4`, `PP07L`, `PP07M`
  * `PP08G`, `PP08G_DSEM`, `PP08G_DMES`, `PP08H`
  * `PP10B1` … `PP10B10`
  * `PP11L2`
* **Paralelos “P_” de agregados DECCF**:

  * `P_DECCF`, `P_RDECCF`, `P_GDECCF`, `P_PDECCF`, `P_IDECCF`, `P_ADECCF`
  * **Coexisten** con la familia `DECCFR*`.

