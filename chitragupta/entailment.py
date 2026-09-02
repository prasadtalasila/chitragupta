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


class EntailmentLabelError(RuntimeError):
    """A configured NLI checkpoint whose `id2label` names no entailment
    label, so there is no column to read a probability out of."""


def optional_stack() -> Any | None:
    """The `CrossEncoder` class, or `None` if sentence_transformers is
    not installed. Same probe shape as overlap_chroma.optional_stack."""
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        return None
    return CrossEncoder


def _entailment_index(id2label: dict) -> int:
    """Which column of a row of logits carries the entailment score.

    Matched case-insensitively (m-67). This module's own docstring
    records that the mapping was confirmed against exactly one
    checkpoint, `cross-encoder/nli-deberta-v3-small`, which spells the
    label `entailment` -- so any other checkpoint is precisely the path
    an exact `== "entailment"` could not read, and `ENTAILMENT` and
    `Entailment` are both common on HuggingFace NLI models.

    A checkpoint whose labels are `LABEL_0`/`LABEL_1`/`LABEL_2` --
    equally common, and what a model card omits when nobody filled the
    mapping in -- deliberately falls through to the raise instead of
    being guessed at. Which logit is entailment is not recoverable from
    an index, and picking one would decide whether a claim reads as
    supported on a coin flip. Refusing by name, in a message carrying
    the setting and the labels the checkpoint actually reports, is the
    only useful answer here; the bare `StopIteration` this replaces
    named neither.
    """
    for index, label in id2label.items():
        if str(label).lower() == "entailment":
            return index
    raise EntailmentLabelError(
        "the NLI checkpoint configured as [enrich].entailment_model, "
        f"{config.ENTAILMENT_MODEL}, reports the labels "
        f"{sorted(str(label) for label in id2label.values())} -- none of them "
        "an entailment label. Claim-support scoring reads the entailment "
        "probability out of the model's own id2label mapping and will not "
        "guess which column that is. Point [enrich].entailment_model (or "
        "ENTAILMENT_MODEL) at a checkpoint whose labels are named, e.g. "
        "cross-encoder/nli-deberta-v3-small."
    )


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
        index = _entailment_index(self.model.model.config.id2label)
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
