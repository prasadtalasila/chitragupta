"""How a setting is read: the TOML load and the typed getters.

Split from `chitragupta/config.py` (#848), which keeps the settings
themselves -- every `config.NAME` a caller reads -- and imports the
getters from here. The split is along what changes: a new setting is an
assignment in `config.py`, a new *kind* of setting is a getter here, and
neither edit now grows the other file.

Imports nothing from `chitragupta`, so it cannot take part in an import
cycle, and `config.py` can import it at the top.

`_toml` lives here, not in `config.py`, because the getters read it from
their own module's globals: a test that wants a getter to see a
different TOML patches `config_load._toml`. `config.py` calls `load()`
on every import of itself, so `importlib.reload(config)` still re-reads
the file, which `tests/test_config.py`'s reload cases depend on.
"""

import math
import os
import tomllib
from pathlib import Path
from typing import Any

_toml: dict = {}


def load(config_path: Path) -> None:
    """Read `config_path` into `_toml`, the source every getter reads.

    config.toml is gitignored per-host data (every user edits the parser
    backend, the paths, the worker count), so a fresh clone genuinely does
    not have one -- this is the first thing a new user hits, not an edge
    case. Deliberately a hard failure rather than a silent fallback to
    config.toml.example: a host quietly running settings its owner never
    chose is a worse failure than one that refuses to start, and it is the
    kind that surfaces days later as "why did it parse with the wrong
    backend". The message carries the literal command because nothing
    about a bare FileNotFoundError traceback suggests the fix.
    """
    global _toml
    try:
        with open(config_path, "rb") as handle:
            _toml = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"No config file at {config_path}. This repo tracks "
            "config.toml.example and gitignores config.toml, so a fresh clone "
            "has to make its own:\n"
            "    cp config.toml.example config.toml\n"
            "then edit it (parser backend, paths, worker count) to suit this "
            "host. Set the CONFIG_PATH env var to use a file somewhere else."
        ) from exc


def _get(env_var: str, *toml_path: str, default: str = "") -> str:
    """A string setting. Raises if the TOML node is present with a
    non-string type instead of silently falling back to `default` --
    `path = 123` in `[bib]` used to mean the default path with no signal
    that the value written was never read."""
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    if not isinstance(raw, str):
        raise ValueError(f"{'/'.join(toml_path)} (or {env_var}) must be a string, not {raw!r}.")
    return raw


def _get_float(env_var: str, *toml_path: str, default: float) -> float:
    """A numeric setting. Raises if the TOML node is present with a
    non-numeric type -- previously silently defaulted, the same
    wrong-typed-value hazard `_get`/`_get_bool` had."""
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    problem = f"{'/'.join(toml_path)} (or {env_var}) must be a number, not {raw!r}."
    if env_var in os.environ:
        try:
            return float(raw)
        except ValueError:
            raise ValueError(problem) from None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(problem)
    return float(raw)


def _get_int(env_var: str, *toml_path: str, default: int) -> int:
    """A whole-number setting, exact. Rejects a fractional value instead
    of silently truncating it: `int(_get_float(...))` used to turn
    `min_tokens = 0.5` into 0 and `topic_min_cluster_size = 3.9` into 3
    with no signal that the config was never an integer.

    A string is parsed with `int()`, not `float()` -- matching
    `_get_positive_int`/`_get_workers`'s existing tolerance for a quoted
    integer, but rejecting `"3.0"`/`"1e3"` as too permissive a reading of
    "whole number", and never losing precision on a large integer string
    the way a float round-trip would.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    problem = f"{'/'.join(toml_path)} (or {env_var}) must be a whole number, not {raw!r}."
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ValueError(problem)
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            raise ValueError(problem) from None
    if isinstance(raw, float):
        if not raw.is_integer():
            raise ValueError(problem)
        return int(raw)
    return raw


def _get_positive_int(env_var: str, *toml_path: str, default: int) -> int:
    """A whole number of at least 1, validated at load.

    Validated rather than silently defaulted -- unlike `_get_float` --
    because the three settings that use it size
    `chitragupta.enrich.embed_index.search()`'s stages, and every
    nonsense value there fails as a *quietly wrong result set* rather
    than as an error: `embed_top_k = 0` returns nothing at all,
    `embed_overfetch_multiplier = 0` asks Chroma for zero rows, and a
    cap of 0 admits no passage from any source. A silent fallback to the
    default would hide all three behind a plausible-looking search.

    `bool` is rejected explicitly for the same reason `_get_workers`
    rejects it: TOML's `embed_top_k = true` parses as a bool, and bool
    is an int subclass, so without this it would quietly mean 1.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    problem = f"{'/'.join(toml_path)} (or {env_var}) must be a whole number >= 1, not {raw!r}."
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ValueError(problem)
    try:
        value = int(str(raw).strip())
    except ValueError:
        raise ValueError(problem) from None
    if value < 1:
        raise ValueError(problem)
    return value


# The integer counterpart of `_get_optional_float` below, off by the same
# explicit word rather than by 0 for the same reason: a
# `support_premise_topk = 0` reads as "score zero premises", which is not
# what "uncapped" means and would empty every premise set if it were ever
# honoured literally. Absent means None too -- unlike
# `_get_optional_float`, no setting using this has a real default, so
# there is no `default` parameter to keep the two cases apart.
#
# A wrapper rather than a fourth hand-rolled validator: a copy of
# `_get_positive_int`'s bool/float/parse rules would cost three times as
# many lines for no behaviour that getter does not already have --
# including the bool-before-int check TOML's `= true` needs.
def _get_optional_positive_int(env_var: str, *toml_path: str) -> "int | None":
    """A whole number of at least 1, or None for "no cap"."""
    raw = _raw_setting(env_var, toml_path)
    if isinstance(raw, str) and raw.strip().lower() in ("", "off", "none", "false"):
        return None
    # `default=0` is a value the setting may never take, which is exactly
    # what makes it usable as "absent": `_get_positive_int` returns its
    # default unvalidated and rejects every *written* value below 1, so a
    # 0 coming back out cannot have come from the config.
    return _get_positive_int(env_var, *toml_path, default=0) or None


def _get_optional_float(
    env_var: str, *toml_path: str, default: "float | None" = None
) -> "float | None":
    """A positive duration in seconds, or None for "no limit".

    _get_float can't express this: it requires a float default, and
    spelling "off" as 0 in a config file reads as "zero seconds", which
    is the opposite of what it means. The off switch is therefore an
    explicit word -- an empty value, "off", "none" or "false" -- and 0 is
    rejected outright rather than quietly reinterpreted.

    `default` applies when the setting is absent entirely. An explicit
    "off" still means off -- the two cases have to stay distinguishable,
    or a setting with a non-None default could never be switched off.

    Validated at load, like _get_workers, so a bad value is reported
    where it was written rather than as a strange timeout much later.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    # Checked for both sources, not just the environment: the shipped
    # config.toml.example writes `document_timeout = "off"`, so the TOML
    # path is the one every new user actually takes.
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.lower() in ("", "off", "none", "false"):
            return None  # explicitly off, regardless of `default`
    # Built once, raised from three places: the three failure modes -- a
    # non-numeric type, an unparseable string, a non-positive or infinite
    # number -- all deserve the same message, and stating it three times
    # is how the copies drift.
    complaint = ValueError(
        f"{'/'.join(toml_path)} (or {env_var}) must be a positive number of "
        f'seconds, or "off", not {raw!r}.'
    )
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise complaint
    try:
        seconds = float(raw)
    except ValueError:
        raise complaint from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise complaint
    return seconds


def _raw_setting(env_var: str, toml_path: tuple[str, ...]) -> Any:
    """The unparsed value of one setting: the env var if set, else the
    TOML node at `toml_path`, else None. Shared lookup for the getters
    that need to distinguish "absent" from every real value."""
    if env_var in os.environ:
        return os.environ[env_var]
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _get_bool(env_var: str, *toml_path: str, default: bool) -> bool:
    """Env vars arrive as strings, so "false"/"0"/"no" have to be read as
    False -- bool("false") is True, which would make every documented way
    of turning a setting off via the environment silently turn it on.

    Raises if the TOML node is present with a non-bool type: a quoted
    `collapse_citations = "false"` used to silently mean the default
    (often True) rather than the False the user wrote."""
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    if env_var in os.environ:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if not isinstance(raw, bool):
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be true or false, not {raw!r}."
        )
    return raw


def _get_workers(env_var: str, *toml_path: str, default: int) -> "int | str":
    """A positive int, or the literal "auto" -- the only setting here
    that isn't a plain str/float/bool.

    Validated at load rather than where the pool is built, because the
    symptom of a bad value there ("0 workers", "-1 workers") surfaces far
    from its cause. `bool` is rejected explicitly: TOML's `workers = true`
    parses as a bool, and bool is an int subclass in Python, so without
    this it would quietly mean "1 worker" instead of being called out.

    Reads through `_raw_setting` like every other getter here. It used to
    restate that walk inline, which left two places for a change to how
    the environment beats the TOML to land (#848).
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    if isinstance(raw, str):
        if raw.strip().lower() == "auto":
            return "auto"
        raw = raw.strip()
    # Built once, raised from three places, for the reason
    # `_get_optional_float` gives: three copies of one message drift.
    complaint = ValueError(
        f'{"/".join(toml_path)} (or {env_var}) must be a positive integer or "auto", not {raw!r}.'
    )
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise complaint
    try:
        workers = int(raw)
    except ValueError:
        raise complaint from None
    if workers < 1:
        raise complaint
    return workers


def _get_choice(env_var: str, *toml_path: str, default: str, choices: tuple[str, ...]) -> str:
    """One of `choices`, matched ignoring case and surrounding space, and
    returned as `choices` spells it -- so `"WARNING"` for a written
    `warning`, and `"forkserver"` for a written `FORKSERVER`.

    Its own loader rather than a bare `_get`, so a typo ("forkserv",
    "WARN") is reported here, naming the alternatives, instead of
    surfacing later as a `ValueError` out of
    `multiprocessing.get_context()` or the logging module, once a pool or
    a handler is already being built. Same reasoning as `_get_workers`.

    One loader for both enum settings, `[parser].start_method` and
    `[logging].level`, which had a copy each that differed only in the
    case they folded to (#848).
    """
    raw = _get(env_var, *toml_path, default=default).strip()
    for choice in choices:
        if choice.lower() == raw.lower():
            return choice
    raise ValueError(
        f"{'/'.join(toml_path)} (or {env_var}) must be one of {', '.join(choices)}, not {raw!r}."
    )
