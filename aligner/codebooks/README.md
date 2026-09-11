# Machine-native official codebook evidence

This directory stores compact, reviewable semantic evidence for source variables used by real EPH/Census alignment.

It is intentionally separate from `aligner/mappings/registry.json`:

- a **codebook record** describes what a source field means in its own producer/relevamiento;
- a **mapping rule** states a proposed directional transformation between source fields;
- a **semantic approval** decides whether the proposed relationship is acceptable for an exact release pair;
- `encuestador-de-hogares` separately decides transport-time admissibility.

A mapping must not be approved from lexical similarity alone.

## Evidence layers

For each variable, prefer three independent layers when available:

1. `machine_definition`: official variable name/label, entity, range/categories and conceptual definition;
2. `questionnaire`: official question wording, response universe/skip logic, and instrument source;
3. `observed_release`: exact release/table presence and observed support summaries.

The first real review pair is:

- EPH `eph-2024-q3-3b6a7a15c4af`;
- CPV-2010 frame `arg-cpv2010-frame-ee6ada167c2d6429`;
- Census sample `census-sample-2024-0839713eafea8d1b`.

## Official sources

EPH:

- INDEC, *Encuesta Permanente de Hogares — Diseño de registro y estructura para las bases preliminares Hogar y Personas*.
- https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_disenoreg_09.pdf

Censo 2010:

- INDEC, *Censo Nacional de Población, Hogares y Viviendas 2010 — Base de datos. Definiciones de la base de datos*.
- https://redatam.indec.gob.ar/redarg/censos/cpv2010rad/Docs/base.pdf
- INDEC, *Cuestionario básico de viviendas particulares*.
- https://www.indec.gob.ar/ftp/cuadros/poblacion/cuestionario_basico_2010.pdf
- REDATAM online dictionary for the 2010 base.

Do not copy whole manuals into the repository. Store compact structured facts plus source URL/page locators so review remains attributable to the official source.
