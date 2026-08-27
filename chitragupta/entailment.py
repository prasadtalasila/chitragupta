"""The one seam that reaches the optional NLI entailment model.

Mirrors chitragupta/overlap_chroma.py's shape: everything else this
aid touches (chitragupta/review/claim_support.py's extraction and
passage lookup) is stdlib-only and testable without the enrich group
present. Only this module has to be probed for.

Needs sentence_transformers.CrossEncoder, which is already part of
the enrich group's sentence-transformers pin (>=5.6,<6.0) -- the
same package chitragupta/overlap_chroma.py's Embedder loads
SentenceTransformer from. No new pyproject.toml entry: CrossEncoder
and SentenceTransformer are two classes in one already-pinned
package.
"""

import math
from typing import Any

from chitragupta import config


def optional_stack() -> Any | None:
    """The `CrossEncoder` class, or `None` if sentence_transformers is
    not installed. Same probe shape as overlap_chroma.optional_stack."""
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        return None
    return CrossEncoder


def _softmax(logits: list[float]) -> list[float]:
    top = max(logits)
    exps = [math.exp(v - top) for v in logits]
    total = sum(exps)
    return [v / total for v in exps]


class Entailer:
    """The NLI cross-encoder, loaded on first use.

    Lazy for the same reason chitragupta/overlap_chroma.py's Embedder
    is lazy: loading it costs real time and memory, and a draft with
    no citations at all must not pay that to find out it has nothing
    to score.

    `.score` takes (premise, hypothesis) pairs and returns the
    entailment probability for each -- softmaxed here rather than
    trusting the model's own `apply_softmax` kwarg, whose availability
    and default have moved across sentence-transformers releases; this
    way the contract is this module's own and stable regardless.

    Confirmed against the real `cross-encoder/nli-deberta-v3-small`
    model (see task-1-report.md): `m.model.config.id2label` is where
    the label mapping lives, and `.predict()` returns raw logits (not
    in [0, 1], row does not sum to 1) -- both exactly as assumed here.
    """

    def __init__(self, model=None) -> None:
        self._model = model

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(config.ENTAILMENT_MODEL)
        return self._model

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        id2label = self.model.model.config.id2label
        index = next(i for i, label in id2label.items() if label == "entailment")
        raw = self.model.predict(list(pairs))
        return [_softmax(list(row))[index] for row in raw]


def unavailable_reason() -> str | None:
    """Why claim-support checking cannot run, or None when it can.

    A sentence, not a code -- printed to a person mid-review, the same
    contract overlap_embed.unavailable_reason() carries for tier 3.
    """
    if optional_stack() is None:
        return (
            "the enrichment layer is not installed -- `poetry install --with enrich` "
            "adds the sentence-transformers package this aid scores with"
        )
    return None


def open_entailer() -> tuple[Entailer | None, str | None]:
    """`(entailer, None)` when this aid can run, `(None, reason)` when
    it cannot. No built index or dossier is needed here, unlike tier
    3 -- only the import has to succeed."""
    reason = unavailable_reason()
    if reason is not None:
        return None, reason
    return Entailer(), None
