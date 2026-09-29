"""chitragupta/render_output/_gate.py: `draft render` gates the draft before any format (#812).

`--format md` used to be the only format that refused a key missing from
the ledger; docx, pdf and tex went to pandoc, which warned and wrote the
document anyway. These pin the gate that now runs first, for every
format, and the no-ledger property the gate itself has.
"""

import pytest

from chitragupta import ledger
from chitragupta.render_output import _gate
from tests.conftest import content_draft, make_reference


def _known(*keys):
    con = ledger.connect()
    for key in keys:
        ledger.upsert_reference(con, make_reference(citekey=key))
    con.commit()
    con.close()


class TestGatedWarnings:
    def test_an_unknown_key_raises_naming_the_key_and_line(self, isolated_config):
        _known("smith2024")
        draft = content_draft(isolated_config, "drafts/x.md")
        text = "Fine [@smith2024].\nBad [@not_a_real_citekey_2026].\n"
        with pytest.raises(_gate.UngatedDraft) as exc:
            _gate.gated_warnings(text, draft)
        assert "not_a_real_citekey_2026" in str(exc.value)
        assert ":2:" in str(exc.value)

    def test_a_known_key_returns_the_draft_warnings_unchanged(self, isolated_config):
        _known("smith2024")
        draft = content_draft(isolated_config, "drafts/x.md")
        assert _gate.gated_warnings("Fine [@smith2024].\n", draft) == []

    def test_a_citation_free_draft_needs_no_ledger(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/x.md")
        assert _gate.gated_warnings("No citations here.\n", draft) == []
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_cited_key_with_no_ledger_is_refused_saying_to_sync(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/x.md")
        with pytest.raises(ledger.NoLedger):
            _gate.gated_warnings("Bad [@not_a_real_citekey_2026].\n", draft)
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_tex_draft_is_read_as_latex(self, isolated_config):
        _known("smith2024")
        draft = content_draft(isolated_config, "drafts/x.tex")
        with pytest.raises(_gate.UngatedDraft):
            _gate.gated_warnings("\\citep{not_a_real_citekey_2026}\n", draft)

    def test_the_refusal_suggests_no_other_key(self, isolated_config):
        # A near-miss real key is exactly what a "did you mean" would
        # offer, and swapping it in would pass the gate for a paper the
        # model never read. The refusal names the bad key and nothing else.
        _known("not_a_real_citekey_2025")
        draft = content_draft(isolated_config, "drafts/x.md")
        with pytest.raises(_gate.UngatedDraft) as exc:
            _gate.gated_warnings("Bad [@not_a_real_citekey_2026].\n", draft)
        assert "not_a_real_citekey_2025" not in str(exc.value)
