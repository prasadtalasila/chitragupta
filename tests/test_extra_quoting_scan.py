import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTheExtraIsQuotedWhereverItIsPrinted:
    SCANNED = ("*.md", "docs/*.md", "chitragupta/**/*.py", "scripts/*.sh", "*.toml")

    UNQUOTED = re.compile(r"(?<!')chitragupta-cli\[[a-z|.]+\](?!')")

    def test_no_unquoted_extra_anywhere_a_reader_can_copy_one(self):
        offenders = []
        for pattern in self.SCANNED:
            for path in sorted(REPO_ROOT.glob(pattern)):
                text = path.read_text(encoding="utf-8")
                for number, line in enumerate(text.splitlines(), start=1):
                    if self.UNQUOTED.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        assert offenders == [], "quote the extra -- zsh globs the brackets:\n" + "\n".join(
            offenders
        )

    def test_the_scan_would_catch_a_regression(self, tmp_path):
        assert self.UNQUOTED.search("run pip install chitragupta-cli[enrich] to get it")
        assert not self.UNQUOTED.search("run pip install 'chitragupta-cli[enrich]' to get it")
