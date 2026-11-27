"""How a setting is read: the TOML load and the typed getters.

Split from `chitragupta/config.py` (#848), which keeps the settings.
Imports nothing from `chitragupta`, so it cannot join an import cycle.
`_toml` lives here because the getters read it from their own globals:
tests patch `config_load._toml`, and `config.py` calls `load()` on every
import, so `importlib.reload(config)` still re-reads the file.
"""

import math
import os
import tomllib
from pathlib import Path
from typing import Any

_toml: dict = {}


def load(config_path: Path) -> None:
    """Read `config_path` into `_toml`, the source every getter reads.

    A hard failure, not a fallback to config.toml.example: a host quietly
    running settings its owner never chose is worse than one that refuses
    to start. The message carries the literal fix command.
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
    non-string type instead of silently falling back to `default`."""
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    if not isinstance(raw, str):
        raise ValueError(f"{'/'.join(toml_path)} (or {env_var}) must be a string, not {raw!r}.")
    return raw


def _get_float(env_var: str, *toml_path: str, default: float) -> float:
    """A numeric setting. Raises if the TOML node is present with a
    non-numeric type."""
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
    of silently truncating it (`min_tokens = 0.5` became 0).

    A string is parsed with `int()`, not `float()`: `"3.0"`/`"1e3"` are
    rejected and a large integer string never loses precision.
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

    Its settings size `embed_index.search()`'s stages, where a 0 fails as
    a quietly empty result rather than an error. `bool` is rejected
    because TOML `true` is an int subclass and would mean 1.
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


# Off by an explicit word, not 0, as `_get_optional_float`: `= 0` would
# read as "score zero premises". Absent means None too. A wrapper so the
# bool/float/parse rules of `_get_positive_int` are not copied.
def _get_optional_positive_int(env_var: str, *toml_path: str) -> "int | None":
    """A whole number of at least 1, or None for "no cap"."""
    raw = _raw_setting(env_var, toml_path)
    if isinstance(raw, str) and raw.strip().lower() in ("", "off", "none", "false"):
        return None
    # `default=0` can only come back from absence: every written value
    # below 1 is rejected.
    return _get_positive_int(env_var, *toml_path, default=0) or None


def _get_optional_float(
    env_var: str, *toml_path: str, default: "float | None" = None
) -> "float | None":
    """A positive duration in seconds, or None for "no limit".

    Off is an explicit word ("", "off", "none", "false"); 0 would read as
    "zero seconds" and is rejected. `default` applies only when absent, so
    a setting with a non-None default can still be switched off.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    # Both sources: config.toml.example itself writes `= "off"`.
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.lower() in ("", "off", "none", "false"):
            return None  # explicitly off, regardless of `default`
    # Built once, raised from three places, so the message cannot drift.
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
    TOML node at `toml_path`, else None."""
    if env_var in os.environ:
        return os.environ[env_var]
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _get_bool(env_var: str, *toml_path: str, default: bool) -> bool:
    """A bool setting. Env strings "false"/"0"/"no" read as False, since
    bool("false") is True.

    A non-bool TOML node raises: `collapse_citations = "false"` silently
    meant the default."""
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    # The environment is held to the same bar (#968): `PARSER_OCR=ture`
    # raises rather than reading as False. Empty is False.
    if env_var in os.environ:
        word = raw.strip().lower()
        if word in ("1", "true", "yes", "on"):
            return True
        if word in ("", "0", "false", "no", "off"):
            return False
    elif isinstance(raw, bool):
        return raw
    raise ValueError(f"{'/'.join(toml_path)} (or {env_var}) must be true or false, not {raw!r}.")


def _get_workers(env_var: str, *toml_path: str, default: int) -> "int | str":
    """A positive int, or the literal "auto".

    Validated at load, since "0 workers" would surface far from its cause.
    `bool` is rejected: TOML `workers = true` would quietly mean 1.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    if isinstance(raw, str):
        if raw.strip().lower() == "auto":
            return "auto"
        raw = raw.strip()
    # Built once, as in `_get_optional_float`.
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
    returned as `choices` spells it.

    A typo is reported here with the alternatives, not later from
    `multiprocessing.get_context()` or logging. The one loader for every
    enum setting (#847, #848).
    """
    raw = _get(env_var, *toml_path, default=default).strip()
    for choice in choices:
        if choice.lower() == raw.lower():
            return choice
    raise ValueError(
        f"{'/'.join(toml_path)} (or {env_var}) must be one of {', '.join(choices)}, not {raw!r}."
    )
