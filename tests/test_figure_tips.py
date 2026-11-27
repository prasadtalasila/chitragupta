from chitragupta.review.figure_layout._tips import house_styles, style_definitions, tips

HOUSE = (
    r"\tikzset{cgedge/.style={draw=cgFlowLine, -{Latex[length=2.6mm, width=2.1mm]},"
    r" shorten >=1.5pt},"
    r" cgback/.style={cgedge, dash pattern=on 2.8pt off 2.2pt},"
    r" cgbar/.style={{Latex}-{Latex}}, cglead/.style={draw=#1Line}}"
)


def test_the_plain_spellings_are_read():
    assert tips("->", {}) == (False, True)
    assert tips("<->, thick", {}) == (True, True)
    assert tips("<-", {}) == (True, False)
    assert tips("|<->|", {}) == (True, True)
    assert tips("thick, draw=red", {}) == (False, False)


def test_an_arrows_meta_tip_is_read():
    assert tips("-{Stealth[length=2mm]}", {}) == (False, True)
    assert tips("-Latex", {}) == (False, True)
    assert tips("Stealth-", {}) == (True, False)


def test_shorten_is_not_a_head():
    assert tips("shorten >=2pt", {}) == (False, False)
    assert tips(">=Stealth", {}) == (False, False)


def test_options_that_merely_contain_a_dash_are_not_heads():
    assert tips("rounded corners, postaction={draw, -}", {}) == (False, False)
    assert tips("Flow-Edge", {}) == (False, False)


def test_a_style_is_followed_through_inheritance():
    styles = style_definitions(HOUSE)

    assert tips("cgback", styles) == (False, True)
    assert tips("cgbar", styles) == (True, True)


def test_a_style_called_with_an_argument_is_looked_up_by_name():
    assert tips("cglead=cgFlow", style_definitions(HOUSE)) == (False, False)


def test_a_hyphenated_style_is_read():
    styles = style_definitions(r"\tikzset{my-arrow/.style={->}}")

    assert tips("my-arrow", styles) == (False, True)


def test_a_later_spec_wins():
    assert tips("cgedge, -", house_styles()) == (False, False)
    assert tips("-, ->", {}) == (False, True)


def test_the_arrows_key_is_read():
    assert tips("arrows=->", {}) == (False, True)
    assert tips("arrows={<-}", {}) == (True, False)
    assert tips("arrows={<}-{>}", {}) == (True, True)


def test_blanked_braces_are_read():
    assert tips("-{}", {}) == (False, True)


def test_a_cycle_of_styles_ends():
    assert tips("a", {"a": "b", "b": "a, ->"}) == (False, True)
    assert tips("x", {"x": "x"}) == (False, False)


def test_the_house_block_defines_cgedge_with_an_end_head():
    styles = house_styles()

    assert tips("cgedge", styles) == (False, True)
    assert tips("cgweak", styles) == (False, True)
    assert tips("cglead", styles) == (False, False)
