"""WCAG 2 contrast, and xcolor's mixing, for `figure check`'s k1 and k2 (#1055).

Shared with tests/test_figure_contrast.py so the proof and the rules compute one
number one way. A colour is `(red, green, blue)`, channels 0 to 1.
"""

RGB = tuple[float, float, float]

WHITE: RGB = (1.0, 1.0, 1.0)

# WCAG 2: 1.4.11 asks 3:1 of a line, 1.4.3 asks 4.5:1 of text and 3:1 of large text.
LINE = 3.0
TEXT = 4.5

# WCAG's large text in PostScript points (18pt, or 14pt bold); a TeX point is
# 1/72.27in, so one of these is 72.27/72 TeX points.
LARGE_PT = 18.0
LARGE_BOLD_PT = 14.0
_TEX_PER_BP = 72.27 / 72


def mix(one: RGB, other: RGB, share: float) -> RGB:
    """xcolor's `one!p!other`, `share` being `p / 100`, channel by channel in RGB."""
    return tuple(share * a + (1 - share) * b for a, b in zip(one, other))


def _luminance(colour: RGB) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in colour)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: RGB, other: RGB) -> float:
    """WCAG 2's contrast ratio, from 1 (the same colour) to 21."""
    light, dark = sorted((_luminance(one), _luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def text_threshold(size_pt: float, bold: bool) -> float:
    """3:1 where WCAG counts `size_pt` text as large, 4.5:1 otherwise."""
    large = LARGE_BOLD_PT if bold else LARGE_PT
    return LINE if size_pt >= large * _TEX_PER_BP else TEXT


def hex_code(colour: RGB) -> str:
    return "#" + "".join(f"{round(channel * 255):02X}" for channel in colour)
