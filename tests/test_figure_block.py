"""The house block's region inside a figure file (#1013): what state it
is in, and what stamping it produces. No TeX, no file walk."""

import re
import tomllib
from pathlib import Path

import pytest

from chitragupta import figure
from chitragupta.figure import State

REPO_ROOT = Path(__file__).resolve().parent.parent
BLOCK = REPO_ROOT / "assets" / "tikz" / "cg-figstyle.tex"
REGISTER = REPO_ROOT / "assets" / "tikz" / "cg-figstyle.versions.toml"

LIBS = "\\usetikzlibrary{arrows.meta,positioning}%\n"
PICTURE = "\\begin{tikzpicture}[cg]\n  \\node[cgbox] (a) {A};\n\\end{tikzpicture}%\n"
HEAD = "% A pipeline.\n"


@pytest.fixture(scope="module")
def house():
    return figure.load_house()


def old_block(house, version=0):
    """A stand-in for a past release: the current block with one value
    changed and its marker naming `version`."""
    marker = f" v{house.version} "
    assert marker in house.text and "0.95pt" in house.text, "old_block's edits no longer land"
    return house.text.replace(marker, f" v{version} ", 1).replace("0.95pt", "0.9pt", 1)


def house_with_history(house):
    """`house`, plus a released v0 that `old_block` reproduces."""
    released = {**house.released, figure.digest(old_block(house)): 0}
    return figure.House(text=house.text, version=house.version, released=released)


class TestTheOldBlockStandIn:
    """`old_block` is a past release only while both of its edits land.
    A `.replace` that matches nothing returns its input unchanged, so a
    marker or value that drifted would hand every test using it the
    current block under another name, and those tests classify by
    digest, so they would stay green."""

    def test_it_refuses_a_marker_it_cannot_renumber(self, house):
        drifted = house.text.replace(f" v{house.version} ", f" v{house.version}.0 ", 1)

        with pytest.raises(AssertionError):
            old_block(figure.House(drifted, house.version, house.released))

    def test_it_refuses_a_value_it_cannot_change(self, house):
        drifted = house.text.replace("0.95pt", "0.96pt")

        with pytest.raises(AssertionError):
            old_block(figure.House(drifted, house.version, house.released))


class TestTheRegisterAndTheBlockAgree:
    def test_the_current_block_is_registered_under_its_own_version(self, house):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert register[f"v{house.version}"] == figure.digest(house.text)

    def test_the_block_names_the_highest_registered_version(self, house):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert house.version == max(int(key[1:]) for key in register)

    def test_every_register_key_is_a_version(self):
        register = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
        assert register and all(re.fullmatch(r"v\d+", key) for key in register)

    def test_the_block_file_is_one_whole_region(self, house):
        region = figure.classify(house.text, house)
        assert (region.state, region.start, region.end) == (State.CURRENT, 0, len(house.text))


class TestClassify:
    def test_no_markers_is_missing(self, house):
        assert figure.classify(HEAD + LIBS + PICTURE, house).state is State.MISSING

    def test_the_current_block_is_current(self, house):
        text = HEAD + house.text + LIBS + PICTURE
        assert figure.classify(text, house).state is State.CURRENT

    def test_a_released_older_block_is_stale(self, house):
        history = house_with_history(house)
        text = HEAD + old_block(house) + LIBS + PICTURE
        assert figure.classify(text, history).state is State.STALE

    def test_one_edited_value_is_modified(self, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1)
        assert figure.classify(HEAD + edited + PICTURE, house).state is State.MODIFIED

    def test_a_style_added_inside_the_markers_is_modified(self, house):
        lines = house.text.splitlines(keepends=True)
        edited = "".join(lines[:-1] + ["\\tikzset{mine/.style={red}}%\n", lines[-1]])
        assert figure.classify(edited + PICTURE, house).state is State.MODIFIED

    def test_a_newer_unknown_version_is_modified_and_keeps_its_number(self, house):
        newer = house.text.replace(f" v{house.version} ", " v9 ", 1)
        region = figure.classify(newer + PICTURE, house)
        assert (region.state, region.marker_version) == (State.MODIFIED, 9)

    def test_crlf_line_endings_alone_do_not_make_it_modified(self, house):
        text = (HEAD + house.text + PICTURE).replace("\n", "\r\n")
        assert figure.classify(text, house).state is State.CURRENT

    def test_a_missing_final_newline_after_the_end_marker_is_still_current(self, house):
        assert figure.classify(house.text.rstrip("\n"), house).state is State.CURRENT

    def test_a_reindented_region_is_modified_not_missing(self, house):
        indented = "".join("  " + line for line in house.text.splitlines(keepends=True))
        assert figure.classify(indented + PICTURE, house).state is State.MODIFIED

    @pytest.mark.parametrize(
        "make",
        [
            lambda b: b.rsplit("% >>> end", 1)[0] + PICTURE,  # start, no end
            lambda b: b.split("\n", 1)[1] + PICTURE,  # end, no start
            lambda b: b + b + PICTURE,  # two regions
            lambda b: b.split("\n", 1)[1] + b.split("\n", 1)[0] + "\n",  # end above start
        ],
        ids=["no-end", "no-start", "twice", "inverted"],
    )
    def test_unpaired_or_repeated_markers_are_malformed(self, house, make):
        assert figure.classify(make(house.text), house).state is State.MALFORMED


class TestStamp:
    def test_a_missing_block_goes_above_the_first_library_line(self, house):
        stamped = figure.stamp(HEAD + LIBS + PICTURE, house)
        assert stamped == HEAD + house.text + LIBS + PICTURE

    def test_with_no_library_line_it_goes_above_the_picture(self, house):
        assert figure.stamp(HEAD + PICTURE, house) == HEAD + house.text + PICTURE

    def test_a_commented_out_library_line_is_not_an_anchor(self, house):
        text = "% \\usetikzlibrary{calc}\n" + PICTURE
        assert figure.stamp(text, house) == "% \\usetikzlibrary{calc}\n" + house.text + PICTURE

    def test_a_file_with_no_picture_cannot_be_stamped(self, house):
        assert figure.stamp("% only a comment\n", house) is None

    def test_a_current_file_comes_back_unchanged(self, house):
        text = HEAD + house.text + LIBS + PICTURE
        assert figure.stamp(text, house) == text

    def test_stamping_twice_is_stamping_once(self, house):
        once = figure.stamp(HEAD + LIBS + PICTURE, house)
        assert figure.stamp(once, house) == once

    def test_a_stale_block_is_replaced_and_nothing_else_moves(self, house):
        history = house_with_history(house)
        text = HEAD + old_block(house) + LIBS + PICTURE
        assert figure.stamp(text, history) == HEAD + house.text + LIBS + PICTURE

    def test_crlf_is_kept_throughout(self, house):
        text = (HEAD + LIBS + PICTURE).replace("\n", "\r\n")
        stamped = figure.stamp(text, house)
        assert stamped == (HEAD + house.text + LIBS + PICTURE).replace("\n", "\r\n")

    @pytest.mark.parametrize("state", ["modified", "malformed"])
    def test_an_edited_or_broken_region_is_never_stamped(self, house, state):
        text = {
            "modified": house.text.replace("0.95pt", "0.9pt", 1) + PICTURE,
            "malformed": house.text + house.text + PICTURE,
        }[state]
        assert figure.stamp(text, house) is None


class TestFinding:
    def test_current_says_nothing(self, house):
        assert figure.finding(house.text + PICTURE, house) is None

    def test_missing_names_the_command(self, house):
        assert "python -m chitragupta figure sync" in figure.finding(PICTURE, house)

    def test_stale_names_both_versions(self, house):
        history = house_with_history(house)
        message = figure.finding(old_block(house) + PICTURE, history)
        assert "v0" in message and f"v{house.version}" in message

    def test_modified_says_sync_will_not_touch_it(self, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1)
        assert "will not touch" in figure.finding(edited + PICTURE, house)

    def test_malformed_says_sync_will_not_touch_it(self, house):
        message = figure.finding(house.text + house.text + PICTURE, house)
        assert "unpaired or repeated" in message and "will not touch" in message

    def test_a_newer_version_says_to_upgrade(self, house):
        newer = house.text.replace(f" v{house.version} ", " v9 ", 1)
        assert "newer" in figure.finding(newer + PICTURE, house)


class TestLoadHouse:
    def test_a_missing_block_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            figure.load_house(block=tmp_path / "absent.tex", register=REGISTER)

    def test_a_block_with_no_start_marker_raises_valueerror(self, tmp_path):
        bad = tmp_path / "b.tex"
        bad.write_text("\\tikzset{}\n", encoding="utf-8")
        with pytest.raises(ValueError):
            figure.load_house(block=bad, register=REGISTER)
