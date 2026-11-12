from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


@lru_cache(maxsize=1)
def _vectorizer() -> HashingVectorizer:
    # Stable, fast, no fitting required; avoids heavyweight model deps.
    return HashingVectorizer(
        n_features=384,
        alternate_sign=False,
        norm="l2",
        lowercase=True,
        analyzer="word",
        ngram_range=(1, 2),
        stop_words="english",
    )


def embed(text: str) -> List[float]:
    if not text:
        return [0.0] * 384
    v = _vectorizer().transform([text])
    arr = v.toarray().astype(np.float64)[0]
    return arr.tolist()

