"""Select C5 named profiles from an already-compiled real Census semantic plane."""
from __future__ import annotations

import pandas as pd

from .composition_profiles import profile_feature_ids
from .real_semantic_plane import _canonical_frame


def census_named_profile_frame(result: dict, profile_id: str) -> pd.DataFrame:
    """Project reviewed Census canonical columns through the shared C5 profile registry.

    The function never recodes Census values itself. It only selects canonical
    series already produced by the existing real semantic compiler. A profile
    containing an EPH-only concept (currently P0_LONG via CH07) fails closed.
    """

    fields = profile_feature_ids(profile_id, result["policy"], side="census")
    return _canonical_frame(result["census_frame"], result["transformed_census"], fields)


__all__ = ["census_named_profile_frame"]
