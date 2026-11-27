"""The one seam that reaches the optional NLI entailment model.

Like chitragupta/overlap_chroma.py: everything else in claim support is
stdlib-only, so only this module is probed for. `CrossEncoder` comes
from the already-pinned sentence-transformers, so no new dependency.
"""

import math
from typing import Any

from chitragupta import config, install


class EntailmentUnavailable(RuntimeError):
    """The entailment model would not load (#977); its message is the
    reason `review support` prints when it reports "not run"."""


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

    Matched case-insensitively (m-67): `ENTAILMENT` and `Entailment` are
    common. `LABEL_0`-style labels raise rather than being guessed: which
    logit is entailment is not recoverable, and a guess would decide
    support on a coin flip.
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
        "ENTAILMENT_MODEL) at a checkpoint whose id2label includes an "
        "entailment class, spelled any way -- an NLI model, in other words, "
        "e.g. cross-encoder/nli-deberta-v3-small."
    )


def _softmax(logits: list[float]) -> list[float]:
    top = max(logits)
    exps = [math.exp(v - top) for v in logits]
    total = sum(exps)
    return [v / total for v in exps]


class Entailer:
    """The NLI cross-encoder, loaded on first use.

    Lazy, like overlap_chroma's Embedder. `.score` returns the entailment
    probability per (premise, hypothesis) pair, softmaxed here rather
    than via `apply_softmax`, whose default has moved across releases.
    Checked against `cross-encoder/nli-deberta-v3-small`: labels live in
    `model.config.id2label` and `.predict()` returns raw logits.
    """

    def __init__(self, model=None) -> None:
        self._model = model

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            # A model that will not load (often no cache and no network)
            # becomes EntailmentUnavailable, so the aid reports "not run"
            # (#977). Broad on purpose: sentence-transformers raises
            # anything from OSError to hub errors.
            try:
                self._model = CrossEncoder(config.ENTAILMENT_MODEL)
            except Exception as exc:
                first_line = str(exc).partition("\n")[0] or type(exc).__name__
                raise EntailmentUnavailable(
                    f"the entailment model {config.ENTAILMENT_MODEL!r} could not be loaded "
                    f"({first_line}) -- set [enrich].entailment_model to one that is available"
                ) from exc
        return self._model

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        index = _entailment_index(self.model.model.config.id2label)
        raw = self.model.predict(list(pairs))
        return [_softmax(list(row))[index] for row in raw]


def unavailable_reason() -> str | None:
    """Why claim-support checking cannot run, or None when it can: a
    sentence for a person, as overlap_embed.unavailable_reason().
    """
    if optional_stack() is None:
        return (
            "the enrichment layer is not installed; it adds the "
            "sentence-transformers package this aid scores with. Run, "
            f"{install.enrich_remedy()}."
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
