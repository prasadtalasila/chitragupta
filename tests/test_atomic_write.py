"""chitragupta/_atomic_write.py: one whole-or-nothing writer for the
parsed text (#894) and the passage sidecar (#844)."""

import os

import pytest

from chitragupta import _atomic_write
from chitragupta._atomic_write import write_atomically


def test_bytes_are_written_as_given(tmp_path):
    """pdftotext's stdout, in whatever encoding poppler chose."""
    target = tmp_path / "k.txt"
    write_atomically(target, b"caf\xe9\f")
    assert target.read_bytes() == b"caf\xe9\f"


def test_text_is_utf_8_whatever_the_locale(tmp_path):
    """Not the locale codec, which is cp1252 on CI's Windows leg and has
    no encoding for this character at all."""
    target = tmp_path / "k.txt"
    write_atomically(target, "Łódź\f")
    assert target.read_bytes() == "Łódź\f".encode("utf-8")


def test_an_existing_file_is_replaced_whole(tmp_path):
    target = tmp_path / "k.txt"
    target.write_bytes(b"old")
    write_atomically(target, b"new")
    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["k.txt"]


def test_a_failed_write_keeps_the_old_file_and_removes_its_temp(tmp_path, monkeypatch):
    """The OSError reaches the caller unchanged -- what it means is the
    caller's to decide -- and nothing is left that could be read as
    output."""
    target = tmp_path / "k.txt"
    target.write_bytes(b"old")

    def full_disk(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(_atomic_write.os, "replace", full_disk)
    with pytest.raises(OSError, match="No space left"):
        write_atomically(target, b"new")
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["k.txt"]


def test_the_temp_name_never_carries_the_target_suffix(tmp_path, monkeypatch):
    """So debris from a killed write -- which no `except` can clean up --
    is never globbed as a `.txt` or a `.passages.json`."""
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(os.path.basename(src))
        real_replace(src, dst)

    monkeypatch.setattr(_atomic_write.os, "replace", spy)
    write_atomically(tmp_path / "k.passages.json", "[]")
    assert not seen[0].endswith(".passages.json")
    assert seen[0].startswith("k.passages.json.tmp-")
