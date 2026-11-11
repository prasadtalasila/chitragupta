"""The demo-recorder skill's `retime_cast.py` (#1188).

It replaces the September recording's two one-off scripts, which each
rewrote an asciinema v2 `.cast`'s timestamps: one compressed a dull
span (the `pip install` scroll) and shifted the rest back, the other
also stretched everything after that span. One span, one speed-up, one
tail factor covers both.

Loaded by path: the skill folder's name has a hyphen, and the skill is
developer-only, so it is not part of the package.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "demo-recorder"
    / "scripts"
    / "retime_cast.py"
)
_SPEC = importlib.util.spec_from_file_location("retime_cast", SCRIPT)
retime_cast = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(retime_cast)

HEADER = {"version": 2, "width": 80, "height": 24}
EVENTS = [
    [0.5, "o", "intro"],
    [1.0, "o", "# 1. install\r\n"],
    [3.0, "o", "Collecting chitragupta-cli\r\n"],
    [5.0, "o", "# 2. sync\r\n"],
    [7.0, "o", "synced\r\n"],
]


def times(events):
    return [ev[0] for ev in events]


class TestRetime:
    def test_speed_up_compresses_the_span_and_shifts_the_tail_back(self):
        out = retime_cast.retime(EVENTS, "# 1.", "# 2.", speed_up=4)
        assert times(out) == [0.5, 1.0, 1.5, 2.0, 4.0]

    def test_tail_stretches_everything_after_the_span(self):
        out = retime_cast.retime(EVENTS, "# 1.", "# 2.", speed_up=4, tail=1.5)
        assert times(out) == [0.5, 1.0, 1.5, 2.0, 5.0]

    def test_the_payloads_and_types_are_untouched(self):
        out = retime_cast.retime(EVENTS, "# 1.", "# 2.", speed_up=2)
        assert [ev[1:] for ev in out] == [ev[1:] for ev in EVENTS]

    def test_the_end_marker_is_looked_for_only_after_the_start(self):
        events = [[0.5, "o", "# 2. early"], *EVENTS]
        out = retime_cast.retime(events, "# 1.", "# 2.", speed_up=4)
        assert times(out) == [0.5, 0.5, 1.0, 1.5, 2.0, 4.0]

    def test_input_events_never_match_a_marker(self):
        events = [[0.2, "i", "# 1."], *EVENTS]
        out = retime_cast.retime(events, "# 1.", "# 2.", speed_up=4)
        assert times(out) == [0.2, 0.5, 1.0, 1.5, 2.0, 4.0]

    def test_a_missing_marker_says_which(self):
        with pytest.raises(SystemExit, match="'# 9.' not found after '# 1.'"):
            retime_cast.retime(EVENTS, "# 1.", "# 9.")

    def test_a_missing_start_marker_says_so(self):
        with pytest.raises(SystemExit, match="'# 0.' not found"):
            retime_cast.retime(EVENTS, "# 0.", "# 2.")


def write_cast(path: Path) -> None:
    lines = [json.dumps(HEADER)] + [json.dumps(ev) for ev in EVENTS]
    path.write_text("\n".join(lines) + "\n\n", encoding="utf-8")


class TestMain:
    def test_writes_the_header_unchanged_and_the_retimed_events(self, tmp_path, capsys):
        src, dst = tmp_path / "in.cast", tmp_path / "out.cast"
        write_cast(src)
        argv = [str(src), str(dst), "--start", "# 1.", "--end", "# 2.", "--speed-up", "4"]
        assert retime_cast.main(argv) == 0
        header, *events = dst.read_text(encoding="utf-8").splitlines()
        assert json.loads(header) == HEADER
        assert times(json.loads(line) for line in events) == [0.5, 1.0, 1.5, 2.0, 4.0]
        assert "7.00s -> 4.00s" in capsys.readouterr().out

    @pytest.mark.parametrize("value", ["0", "-2", "x"])
    def test_a_factor_must_be_a_positive_number(self, tmp_path, value, capsys):
        src = tmp_path / "in.cast"
        write_cast(src)
        with pytest.raises(SystemExit) as raised:
            retime_cast.main(
                [str(src), str(tmp_path / "o"), "--start", "a", "--end", "b", "--tail", value]
            )
        assert raised.value.code == 2
        assert "positive number" in capsys.readouterr().err
