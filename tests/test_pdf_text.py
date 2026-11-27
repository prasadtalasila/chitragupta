import enum
import importlib.machinery
import importlib.util
import io
import json
import logging
import multiprocessing
import pickle
import shutil
import signal
import subprocess
import sys
import types
from pathlib import Path

import pytest

from chitragupta import config, install, passages, pdf_text


class TestExtractTextPdftotext:
    @pytest.fixture(autouse=True)
    def _pdftotext_present(self, programs_on_path):
        pass

    def test_calls_pdftotext_with_layout_flag(self, isolated_config, monkeypatch, tmp_path):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"extracted text", stderr=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = pdf_text.extract_text(str(tmp_path / "in.pdf"), "smith_2024")

        assert calls[0][0] == "/usr/bin/pdftotext"
        assert "-layout" in calls[0]
        assert calls[0][-1] == "-"
        assert result == isolated_config.PARSED_DIR / "smith_2024.txt"
        assert result.read_text() == "extracted text"

    def test_creates_parsed_dir(self, isolated_config, monkeypatch, tmp_path):
        assert not isolated_config.PARSED_DIR.exists()

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)
        pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")
        assert isolated_config.PARSED_DIR.exists()

    def test_called_process_error_becomes_extraction_error(
        self, isolated_config, monkeypatch, tmp_path
    ):
        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr=b"pdftotext: bad PDF")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(pdf_text.ExtractionError, match="bad PDF"):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")


class FakeTextItem:
    def __init__(self, text, label="text", page=1):
        self.text = text
        self.label = label
        self.prov = [types.SimpleNamespace(page_no=page, bbox=None)]


class FakeDoclingDocument:
    def __init__(self, markdown, texts=None):
        self._pages = markdown if isinstance(markdown, list) else [markdown]
        self.texts = texts or []

    def export_to_markdown(self, page_break_placeholder=None):
        return (page_break_placeholder or "\n\n").join(self._pages)


class FakeDoclingResult:
    def __init__(self, markdown, texts=None):
        self.document = FakeDoclingDocument(markdown, texts)
        self.status = types.SimpleNamespace(name="SUCCESS")


class FakeDoclingConverter:
    last_convert_path = None
    build_count = 0
    last_format_options = None
    next_pages = None
    next_texts = None

    def __init__(self, format_options=None):
        FakeDoclingConverter.build_count += 1
        FakeDoclingConverter.last_format_options = format_options
        options = getattr((format_options or {}).get("pdf"), "pipeline_options", None)
        accelerator = getattr(options, "accelerator_options", None)
        self.device = getattr(accelerator, "device", None)

    def convert(self, pdf_path):
        FakeDoclingConverter.last_convert_path = pdf_path
        if "explode" in str(pdf_path):
            raise RuntimeError("simulated docling failure")
        if "cudaoom" in str(pdf_path) and self.device != "cpu":
            raise RuntimeError("CUDA error: out of memory")
        if "alwaysoom" in str(pdf_path):
            raise RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB")
        return FakeDoclingResult(
            FakeDoclingConverter.next_pages or f"# Parsed content of {pdf_path}",
            FakeDoclingConverter.next_texts,
        )

    @staticmethod
    def pipeline_options():
        return FakeDoclingConverter.last_format_options["pdf"].pipeline_options


@pytest.fixture
def fake_docling(monkeypatch):
    FakeDoclingConverter.last_convert_path = None
    FakeDoclingConverter.build_count = 0
    FakeDoclingConverter.last_format_options = None
    FakeDoclingConverter.next_pages = None
    FakeDoclingConverter.next_texts = None
    pdf_text._reset_docling_converter()

    fake_submodule = types.ModuleType("docling.document_converter")
    fake_submodule.DocumentConverter = FakeDoclingConverter
    fake_submodule.PdfFormatOption = lambda pipeline_options=None: types.SimpleNamespace(
        pipeline_options=pipeline_options
    )
    fake_submodule.__spec__ = importlib.machinery.ModuleSpec(
        "docling.document_converter", loader=None
    )
    fake_package = types.ModuleType("docling")
    fake_package.__spec__ = importlib.machinery.ModuleSpec("docling", loader=None)
    base_models = types.ModuleType("docling.datamodel.base_models")
    base_models.InputFormat = types.SimpleNamespace(PDF="pdf")
    pipeline_options = types.ModuleType("docling.datamodel.pipeline_options")
    pipeline_options.PdfPipelineOptions = lambda: types.SimpleNamespace(
        do_ocr=True,
        do_formula_enrichment=False,
        accelerator_options=None,
        document_timeout=None,
    )
    accelerator = types.ModuleType("docling.datamodel.accelerator_options")
    accelerator.AcceleratorOptions = lambda num_threads=None, device=None: types.SimpleNamespace(
        num_threads=num_threads, device=device
    )

    for name, mod in [
        ("docling", fake_package),
        ("docling.document_converter", fake_submodule),
        ("docling.datamodel", types.ModuleType("docling.datamodel")),
        ("docling.datamodel.base_models", base_models),
        ("docling.datamodel.pipeline_options", pipeline_options),
        ("docling.datamodel.accelerator_options", accelerator),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr(config, "PARSER", "docling")
    yield FakeDoclingConverter
    pdf_text._reset_docling_converter()


class TestDoclingOcrSetting:
    def test_ocr_is_off_by_default(self, isolated_config, fake_docling, tmp_path):
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert fake_docling.pipeline_options().do_ocr is False

    def test_ocr_can_be_turned_back_on(self, isolated_config, fake_docling, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER_OCR", True)
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert fake_docling.pipeline_options().do_ocr is True


class TestDoclingFormulaSetting:
    def test_formula_enrichment_is_off_by_default(self, isolated_config, fake_docling, tmp_path):
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert fake_docling.pipeline_options().do_formula_enrichment is False

    def test_formula_enrichment_can_be_turned_on(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER_FORMULAS", True)
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert fake_docling.pipeline_options().do_formula_enrichment is True


class TestDoclingConverterReuse:
    def test_converter_is_built_once_across_calls(self, isolated_config, fake_docling, tmp_path):
        for i in range(3):
            pdf_text.extract_text(str(tmp_path / f"paper{i}.pdf"), f"key_{i}")
        assert fake_docling.build_count == 1

    def test_changing_the_ocr_setting_rebuilds_the_converter(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert fake_docling.build_count == 1

        monkeypatch.setattr(config, "PARSER_OCR", True)
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "b")
        assert fake_docling.build_count == 2
        assert fake_docling.pipeline_options().do_ocr is True

    def test_changing_the_formula_setting_rebuilds_the_converter(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert fake_docling.build_count == 1

        monkeypatch.setattr(config, "PARSER_FORMULAS", True)
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "b")
        assert fake_docling.build_count == 2
        assert fake_docling.pipeline_options().do_formula_enrichment is True

    def test_a_failed_convert_does_not_discard_the_converter(
        self, isolated_config, fake_docling, tmp_path
    ):
        with pytest.raises(pdf_text.ExtractionError):
            pdf_text.extract_text(str(tmp_path / "explode.pdf"), "bad")
        pdf_text.extract_text(str(tmp_path / "fine.pdf"), "good")
        assert fake_docling.build_count == 1


class TestExtractTextDocling:
    def test_writes_markdown_output(self, isolated_config, fake_docling, tmp_path):
        pdf = tmp_path / "paper.pdf"
        result = pdf_text.extract_text(str(pdf), "smith_2024")

        assert result == isolated_config.PARSED_DIR / "smith_2024.txt"
        assert "Parsed content" in result.read_text()
        assert FakeDoclingConverter.last_convert_path == str(pdf)

    def test_backend_exception_becomes_extraction_error(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf = tmp_path / "explode.pdf"
        with pytest.raises(pdf_text.ExtractionError, match="simulated docling failure"):
            pdf_text.extract_text(str(pdf), "key")

    def test_broken_transitive_dependency_becomes_missing_dependency(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER", "docling")
        fake_package = types.ModuleType("docling")
        fake_package.__spec__ = importlib.machinery.ModuleSpec("docling", loader=None)
        broken_submodule = types.ModuleType(
            "docling.document_converter"
        )  # no DocumentConverter attribute
        monkeypatch.setitem(sys.modules, "docling", fake_package)
        monkeypatch.setitem(sys.modules, "docling.document_converter", broken_submodule)

        with pytest.raises(pdf_text.MissingDependency, match="docling"):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")


class TestAWriteFailureIsTransient:
    def test_the_parsed_text_write(self, isolated_config, fake_docling, tmp_path, monkeypatch):
        real_write_text = Path.write_text

        def full_disk(self, *args, **kwargs):
            if ".txt" in self.name:
                raise OSError(28, "No space left on device")
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", full_disk)
        with pytest.raises(pdf_text.ExtractionError, match="No space left") as caught:
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert caught.value.transient is True
        assert isinstance(caught.value.__cause__, OSError)

    def test_the_passages_sidecar_write(self, isolated_config, fake_docling, tmp_path, monkeypatch):
        def denied(citekey, records):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(passages, "write_sidecar", denied)
        with pytest.raises(pdf_text.ExtractionError, match="Permission denied") as caught:
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert caught.value.transient is True

    def test_preparing_the_output_directory(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        def denied(citekey):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(passages, "clear_sidecar", denied)
        with pytest.raises(pdf_text.ExtractionError, match="Permission denied") as caught:
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert caught.value.transient is True

    def test_an_oserror_outside_a_write_is_not_reworded_as_one(
        self, isolated_config, monkeypatch, tmp_path
    ):
        def extractor(pdf_path, out_path, threads=None):
            raise FileNotFoundError(2, "No such file or directory", "pdftotext")

        monkeypatch.setitem(pdf_text._EXTRACTORS, "pdftotext", extractor)
        monkeypatch.setattr(pdf_text, "is_available", lambda: True)
        with pytest.raises(FileNotFoundError):
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")

    def test_a_backend_failure_is_still_not_transient(
        self, isolated_config, fake_docling, tmp_path
    ):
        with pytest.raises(pdf_text.ExtractionError) as caught:
            pdf_text.extract_text(str(tmp_path / "explode.pdf"), "key")
        assert getattr(caught.value, "transient", False) is False


class TestTheParsedTextIsWrittenWholeOrNotAtAll:
    @pytest.fixture
    def pdftotext_prints(self, isolated_config, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=b"page one\f", stderr=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)

    @pytest.fixture(params=["pdftotext", "docling"])
    def either_backend(self, request, isolated_config):
        return request.getfixturevalue(
            "pdftotext_prints" if request.param == "pdftotext" else "fake_docling"
        )

    @staticmethod
    def _torn_write(monkeypatch):
        real_bytes, real_text = Path.write_bytes, Path.write_text

        def torn(real, half):
            def write(self, data, *args, **kwargs):
                if ".txt" in self.name:
                    real(self, half(data), *args, **kwargs)
                    raise OSError(28, "No space left on device")
                return real(self, data, *args, **kwargs)

            return write

        monkeypatch.setattr(Path, "write_bytes", torn(real_bytes, lambda d: d[: len(d) // 2]))
        monkeypatch.setattr(Path, "write_text", torn(real_text, lambda d: d[: len(d) // 2]))

    def test_pdftotext_output_is_written_byte_for_byte(self, pdftotext_prints, tmp_path):
        out = pdf_text.extract_text(str(tmp_path / "in.pdf"), "smith_2024")
        assert out.read_bytes() == b"page one\f"

    def test_a_full_disk_is_transient_under_either_backend(
        self, either_backend, monkeypatch, tmp_path
    ):
        self._torn_write(monkeypatch)
        with pytest.raises(pdf_text.ExtractionError, match="No space left") as caught:
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert caught.value.transient is True

    def test_a_torn_write_leaves_no_text_and_no_debris(self, either_backend, monkeypatch, tmp_path):
        self._torn_write(monkeypatch)
        with pytest.raises(pdf_text.ExtractionError):
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert [p.name for p in config.PARSED_DIR.iterdir() if ".txt" in p.name] == []

    def test_a_failed_rewrite_keeps_the_previous_text_whole(
        self, either_backend, monkeypatch, tmp_path
    ):
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        previous = config.PARSED_DIR / "smith_2024.txt"
        previous.write_text("the previous parse", encoding="utf-8")
        self._torn_write(monkeypatch)
        with pytest.raises(pdf_text.ExtractionError):
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert previous.read_bytes() == b"the previous parse"

    def test_a_failed_pdftotext_run_is_still_permanent(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr=b"Syntax Error: bad xref")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(pdf_text.ExtractionError, match="bad xref") as caught:
            pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert getattr(caught.value, "transient", False) is False
        assert not (config.PARSED_DIR / "smith_2024.txt").exists()


class TestDoclingPageBreaks:
    def test_pages_are_separated_by_form_feeds(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDoclingConverter, "next_pages", ["first page", "second page", "third page"]
        )
        out = pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert out.read_text().split("\f") == ["first page", "second page", "third page"]

    def test_the_split_gives_one_based_page_numbers(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(FakeDoclingConverter, "next_pages", ["alpha", "beta", "gamma"])
        out = pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        pages = out.read_text().split("\f")
        assert pages[2 - 1] == "beta"

    def test_the_form_feed_does_not_disturb_the_quality_warning(self, isolated_config):
        without = pdf_text.run_together_ratio("alpha beta gamma delta")
        assert pdf_text.run_together_ratio("alpha beta\fgamma delta") == without


@pytest.mark.usefixtures("programs_on_path")
class TestCorpusLayerPassageSidecar:
    @staticmethod
    def _texts():
        return [FakeTextItem("A reading-ordered paragraph.", page=3)]

    def test_a_docling_parse_writes_one(self, isolated_config, fake_docling, tmp_path, monkeypatch):
        monkeypatch.setattr(FakeDoclingConverter, "next_texts", self._texts())
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")

        records = json.loads(passages.sidecar_path("smith_2024").read_text())
        assert records == [{"text": "A reading-ordered paragraph.", "label": "text", "page": 3}]

    def test_it_sits_beside_the_parsed_text(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(FakeDoclingConverter, "next_texts", self._texts())
        out = pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert passages.sidecar_path("smith_2024").parent == out.parent

    def test_pdftotext_writes_none(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(pdf_text, "is_available", lambda: True)
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout="", stderr="")
        )
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert not passages.sidecar_path("smith_2024").exists()

    def test_switching_to_pdftotext_removes_a_stale_one(
        self, isolated_config, monkeypatch, tmp_path
    ):
        passages.write_sidecar("smith_2024", [{"text": "From the docling run.", "page": 1}])
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(pdf_text, "is_available", lambda: True)
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout="", stderr="")
        )

        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert not passages.sidecar_path("smith_2024").exists()

    def test_a_failed_parse_removes_a_stale_one(self, isolated_config, fake_docling, tmp_path):
        passages.write_sidecar("smith_2024", [{"text": "From last week.", "page": 1}])

        with pytest.raises(pdf_text.ExtractionError):
            pdf_text.extract_text(str(tmp_path / "explode.pdf"), "smith_2024")

        assert not passages.sidecar_path("smith_2024").exists()

    def test_a_reparse_replaces_rather_than_merges(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDoclingConverter, "next_texts", [FakeTextItem("Original wording.", page=1)]
        )
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")

        monkeypatch.setattr(
            FakeDoclingConverter, "next_texts", [FakeTextItem("Revised wording.", page=1)]
        )
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")

        records = json.loads(passages.sidecar_path("smith_2024").read_text())
        assert [r["text"] for r in records] == ["Revised wording."]

    def test_a_document_with_no_prose_still_writes_an_empty_sidecar(
        self, isolated_config, fake_docling, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            FakeDoclingConverter,
            "next_texts",
            [FakeTextItem("Journal of Things", label="page_header")],
        )
        pdf_text.extract_text(str(tmp_path / "paper.pdf"), "smith_2024")
        assert json.loads(passages.sidecar_path("smith_2024").read_text()) == []

    def test_an_empty_sidecar_does_not_capture_the_ladder(
        self, isolated_config, fake_docling, tmp_path
    ):
        assert passages._from_sidecar(passages.sidecar_path("smith_2024")) is None
        passages.write_sidecar("smith_2024", [])
        assert passages._from_sidecar(passages.sidecar_path("smith_2024")) is None


class TestIsAvailable:
    def test_true_when_pdftotext_on_path(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")
        assert pdf_text.is_available() is True

    def test_false_when_pdftotext_missing(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert pdf_text.is_available() is False

    def test_true_when_docling_importable(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(pdf_text.importlib.util, "find_spec", lambda name: object())
        assert pdf_text.is_available() is True

    def test_false_when_docling_not_importable(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(pdf_text.importlib.util, "find_spec", lambda name: None)
        assert pdf_text.is_available() is False


class TestUnavailableReason:
    def test_pdftotext_mentions_poppler(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        assert "poppler-utils" in pdf_text.unavailable_reason()

    def test_docling_mentions_enrich_group(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "docling")
        assert install.enrich_remedy() in pdf_text.unavailable_reason()


class TestDropStdlibShadowingPathEntries:
    def test_removes_an_entry_that_shadows_a_stdlib_module(self, tmp_path, monkeypatch):
        shadowing = tmp_path / "site-packages" / "cv2"
        (shadowing / "typing").mkdir(parents=True)
        (shadowing / "typing" / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", ["", str(tmp_path), str(shadowing)])

        removed = pdf_text.drop_stdlib_shadowing_path_entries()

        assert removed == [str(shadowing)]
        assert str(shadowing) not in sys.path
        assert str(tmp_path) in sys.path  # unrelated entries are left alone

    def test_a_package_directory_outside_site_packages_is_left_alone(self, tmp_path, monkeypatch):
        project = tmp_path / "my-project" / "vendor"
        (project / "typing").mkdir(parents=True)
        (project / "typing" / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", [str(project)])

        assert pdf_text.drop_stdlib_shadowing_path_entries() == []
        assert str(project) in sys.path

    def test_a_site_packages_entry_without_a_shadowing_name_is_kept(self, tmp_path, monkeypatch):
        harmless = tmp_path / "site-packages" / "requests"
        harmless.mkdir(parents=True)
        (harmless / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", [str(harmless)])

        assert pdf_text.drop_stdlib_shadowing_path_entries() == []
        assert str(harmless) in sys.path

    def test_never_removes_site_packages_itself(self, tmp_path, monkeypatch):
        site = tmp_path / "site-packages"
        (site / "typing").mkdir(parents=True)
        (site / "typing" / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", [str(site)])

        assert pdf_text.drop_stdlib_shadowing_path_entries() == []
        assert str(site) in sys.path

    def test_an_empty_entry_is_skipped(self, monkeypatch):
        monkeypatch.setattr(sys, "path", ["", "/nonexistent"])

        assert pdf_text.drop_stdlib_shadowing_path_entries() == []
        assert sys.path == ["", "/nonexistent"]

    def test_the_pool_context_sanitises_before_children_are_created(self, tmp_path, monkeypatch):
        shadowing = tmp_path / "site-packages" / "cv2"
        (shadowing / "typing").mkdir(parents=True)
        (shadowing / "typing" / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", ["", str(shadowing)])

        pdf_text.process_pool_context()

        assert str(shadowing) not in sys.path


class TestExtractTextMissingBinary:
    def test_raises_missing_binary_instead_of_file_not_found(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(pdf_text.MissingBinary, match="pdftotext"):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")

    def test_does_not_invoke_subprocess_when_binary_missing(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(shutil, "which", lambda name: None)

        def fail_if_called(cmd, **kwargs):
            raise AssertionError("subprocess.run should not be called when pdftotext is missing")

        monkeypatch.setattr(subprocess, "run", fail_if_called)
        with pytest.raises(pdf_text.MissingBinary):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")


class TestExtractTextMissingDependency:
    def test_raises_missing_dependency_for_docling(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(pdf_text.importlib.util, "find_spec", lambda name: None)
        with pytest.raises(pdf_text.MissingDependency, match="docling"):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")

    def test_missing_dependency_is_a_backend_unavailable(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(pdf_text.importlib.util, "find_spec", lambda name: None)
        with pytest.raises(pdf_text.BackendUnavailable):
            pdf_text.extract_text(str(tmp_path / "in.pdf"), "key")


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
class TestExtractTextReal:
    def test_real_pdftotext_on_a_real_pdf(self, isolated_config, tmp_path):
        pandoc = shutil.which("pandoc")
        pdflatex = shutil.which("pdflatex")
        if not pandoc or not pdflatex:
            pytest.skip("pandoc/pdflatex not installed -- can't generate a fixture PDF")

        md = tmp_path / "doc.md"
        md.write_text("# Hello\n\nThis is a real test PDF.\n")
        pdf = tmp_path / "doc.pdf"
        subprocess.run(
            ["pandoc", str(md), "-o", str(pdf), "--pdf-engine=pdflatex"],
            check=True,
            capture_output=True,
        )

        result = pdf_text.extract_text(str(pdf), "real_key")
        assert result.exists()
        assert "real test PDF" in result.read_text()


class TestParseQualityGuard:
    HEALTHY = " ".join(["the quick brown fox jumps over a lazy dog"] * 40)

    def test_clean_text_produces_no_warning(self, isolated_config):
        assert pdf_text.quality_warning(self.HEALTHY) is None

    def test_fused_words_produce_a_warning(self, isolated_config):
        fused = self.HEALTHY + " " + " ".join(["isaninputtooranoutputfromafunction"] * 30)
        warning = pdf_text.quality_warning(fused)
        assert warning is not None
        assert "losing spaces" in warning

    def test_short_documents_are_not_judged(self, isolated_config):
        assert pdf_text.quality_warning("averyverylongfusedtokenindeedyes short") is None

    def test_empty_text_is_not_a_crash(self, isolated_config):
        assert pdf_text.run_together_ratio("") == (0.0, 0)
        assert pdf_text.quality_warning("") is None

    def test_ratio_counts_only_alphabetic_runs(self, isolated_config):
        digits = " ".join(["10.1000/abcd1234567890123456789"] * 60)
        ratio, total = pdf_text.run_together_ratio(digits)
        assert ratio == 0.0
        assert total > 0

    def test_counts_non_ascii_letters_as_letters(self, isolated_config):
        text = " ".join(
            ["Schr\u00f6der", "W\u00fcllnerstra\u00dfe", "\u03b1\u03b2\u03b3\u03b4"] * 100
        )
        ratio, total = pdf_text.run_together_ratio(text)

        assert total == 300, "accented and Greek words must count as single tokens"
        assert ratio == 0.0

    def test_fusion_is_still_detected_in_non_ascii_text(self, isolated_config):
        fused = " ".join(["\u00fcbersetzungsfehlerbeispielwortkette"] * 250)
        assert pdf_text.quality_warning(fused) is not None

    def test_threshold_is_configurable(self, isolated_config, monkeypatch):
        fused = " ".join(["averylongfusedtokenhere"] * 5 + ["ok"] * 295)
        monkeypatch.setattr(isolated_config, "PARSE_LONG_WORD_RATIO", 0.5)
        assert pdf_text.quality_warning(fused) is None
        monkeypatch.setattr(isolated_config, "PARSE_LONG_WORD_RATIO", 0.001)
        assert pdf_text.quality_warning(fused) is not None


class TestPageCount:
    def test_single_page_has_no_form_feed(self):
        assert pdf_text.page_count("no page breaks here") == 1

    def test_counts_one_more_than_form_feeds_between_pages(self):
        assert pdf_text.page_count("page one\fpage two\fpage three") == 3

    def test_a_trailing_form_feed_does_not_inflate_the_count(self):
        assert pdf_text.page_count("page one\fpage two\fpage three\f") == 3

    def test_empty_text_counts_as_one_page(self):
        assert pdf_text.page_count("") == 1


class TestAllowedCpus:
    def test_uses_affinity_when_available(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing.os, "cpu_count", lambda: 96)
        monkeypatch.setattr(
            pdf_text._sizing.os, "sched_getaffinity", lambda pid: set(range(48)), raising=False
        )
        assert pdf_text.allowed_cpus() == 48

    def test_falls_back_to_cpu_count_without_affinity(self, monkeypatch):
        monkeypatch.delattr(pdf_text._sizing.os, "sched_getaffinity", raising=False)
        monkeypatch.setattr(pdf_text._sizing.os, "cpu_count", lambda: 8)
        assert pdf_text.allowed_cpus() == 8

    def test_falls_back_to_one_when_cpu_count_is_unknown(self, monkeypatch):
        monkeypatch.delattr(pdf_text._sizing.os, "sched_getaffinity", raising=False)
        monkeypatch.setattr(pdf_text._sizing.os, "cpu_count", lambda: None)
        assert pdf_text.allowed_cpus() == 1


class TestWorkerCeiling:
    def test_docling_charges_four_cpus_per_worker(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        assert pdf_text.worker_ceiling(docling=True) == 12

    def test_pdftotext_gets_one_per_cpu(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        assert pdf_text.worker_ceiling(docling=False) == 48

    @pytest.mark.parametrize("cpus,expected", [(1, 1), (4, 1), (8, 2), (16, 4), (48, 12)])
    def test_the_table_the_docs_promise(self, monkeypatch, cpus, expected):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: cpus)
        assert pdf_text.worker_ceiling(docling=True) == expected

    def test_never_below_one(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 1)
        assert pdf_text.worker_ceiling(docling=True) == 1

    def test_docling_regardless_of_config_parser(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        assert pdf_text.worker_ceiling(docling=True) == 12


class TestResolveWorkers:
    @pytest.fixture(autouse=True)
    def _host(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)

    def test_default_of_one_stays_one(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", 1)
        assert pdf_text.resolve_workers(500, docling=True) == (1, None)

    def test_auto_divides_cpus_by_the_cost_of_a_docling_worker(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        assert pdf_text.resolve_workers(500, docling=True) == (12, None)

    @pytest.mark.parametrize("cpus,expected", [(4, 1), (8, 2), (16, 4), (48, 12)])
    def test_auto_on_small_hosts(self, monkeypatch, cpus, expected):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: cpus)
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        assert pdf_text.resolve_workers(500, docling=True)[0] == expected

    def test_oversized_request_is_clamped_and_explained(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 8)
        monkeypatch.setattr(config, "PARSER_WORKERS", 15)
        workers, note = pdf_text.resolve_workers(500, docling=True)
        assert workers == 2
        assert "15" in note
        assert "2" in note
        assert "8" in note

    def test_request_within_the_ceiling_is_not_explained(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        assert pdf_text.resolve_workers(500, docling=True) == (4, None)

    def test_never_more_workers_than_documents(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        assert pdf_text.resolve_workers(3, docling=True)[0] == 3

    def test_no_documents_still_resolves_to_one(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        assert pdf_text.resolve_workers(0, docling=True)[0] == 1

    def test_pdftotext_worker_is_not_charged_four_cpus(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        assert pdf_text.resolve_workers(500, docling=False)[0] == 48

    def test_docling_regardless_of_config_parser(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 8)
        monkeypatch.setattr(config, "PARSER_WORKERS", 15)
        workers, note = pdf_text.resolve_workers(500, docling=True)
        assert workers == 2
        assert "per docling worker" in note


class TestDoclingThreads:
    def test_one_worker_keeps_doclings_own_default(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        assert pdf_text.docling_threads(1) == 4

    def test_threads_divide_down_so_the_product_fits_the_host(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 8)
        assert pdf_text.docling_threads(4) == 2

    def test_never_below_one(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 4)
        assert pdf_text.docling_threads(12) == 1


class TestDoclingThreadBudget:
    def test_no_thread_budget_leaves_doclings_own_accelerator_settings(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert fake_docling.pipeline_options().accelerator_options is None

    def test_thread_budget_is_applied_to_the_pipeline(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a", threads=2)
        assert fake_docling.pipeline_options().accelerator_options.num_threads == 2

    def test_a_different_budget_rebuilds_the_converter(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a", threads=2)
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "b", threads=4)
        assert fake_docling.build_count == 2


class TestExtractOne:
    def test_success_returns_the_output_path(self, isolated_config, fake_docling, tmp_path):
        citekey, out_path, exc = pdf_text.extract_one((str(tmp_path / "a.pdf"), "a", None))
        assert citekey == "a"
        assert exc is None
        assert Path(out_path).read_text().startswith("# Parsed content")

    def test_failure_returns_the_exception_with_its_type_intact(
        self, isolated_config, fake_docling, tmp_path
    ):
        citekey, out_path, exc = pdf_text.extract_one((str(tmp_path / "explode.pdf"), "bad", None))
        assert citekey == "bad"
        assert out_path is None
        assert isinstance(exc, pdf_text.ExtractionError)

    def test_backend_unavailable_keeps_its_own_type(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(pdf_text, "is_available", lambda: False)
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        _, _, exc = pdf_text.extract_one((str(tmp_path / "a.pdf"), "a", None))
        assert isinstance(exc, pdf_text.BackendUnavailable)

    def test_the_returned_exception_survives_pickling(
        self, isolated_config, fake_docling, tmp_path
    ):
        import pickle

        _, _, exc = pdf_text.extract_one((str(tmp_path / "explode.pdf"), "bad", None))
        assert isinstance(pickle.loads(pickle.dumps(exc)), pdf_text.ExtractionError)


def _fake_nvidia_smi(monkeypatch, n_gpus=None, returncode=0, raises=None, found=True):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/nvidia-smi" if found else None)

    def fake_run(cmd, **kwargs):
        if raises is not None:
            raise raises
        lines = "".join(f"GPU {i}: NVIDIA A40 (UUID: GPU-{i})\n" for i in range(n_gpus or 0))
        return subprocess.CompletedProcess(cmd, returncode, stdout=lines, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)


class TestGpuCount:
    def test_zero_when_the_pool_is_not_docling(self):
        assert pdf_text.gpu_count(docling=False) == 0

    def test_counts_the_gpus_nvidia_smi_lists(self, monkeypatch):
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        _fake_nvidia_smi(monkeypatch, n_gpus=4)
        assert pdf_text.gpu_count(docling=True) == 4

    def test_counting_does_not_import_torch(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "torch", raising=False)
        _fake_nvidia_smi(monkeypatch, n_gpus=2)

        pdf_text.gpu_count(docling=True)

        assert "torch" not in sys.modules

    def test_falls_back_to_torch_when_nvidia_smi_is_absent(self, monkeypatch):
        _fake_nvidia_smi(monkeypatch, found=False)
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda: 3)),
        )
        assert pdf_text.gpu_count(docling=True) == 3

    def test_a_failing_nvidia_smi_falls_back_too(self, monkeypatch):
        _fake_nvidia_smi(monkeypatch, n_gpus=0, returncode=9)
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda: 1)),
        )
        assert pdf_text.gpu_count(docling=True) == 1

    def test_a_hanging_nvidia_smi_does_not_hang_the_sync(self, monkeypatch):
        _fake_nvidia_smi(monkeypatch, raises=subprocess.TimeoutExpired(["nvidia-smi"], 10))
        monkeypatch.setitem(sys.modules, "torch", None)
        assert pdf_text.gpu_count(docling=True) == 0

    def test_zero_when_neither_nvidia_smi_nor_torch_can_answer(self, monkeypatch):
        _fake_nvidia_smi(monkeypatch, found=False)
        monkeypatch.setitem(sys.modules, "torch", None)
        assert pdf_text.gpu_count(docling=True) == 0

    def test_a_broken_cuda_runtime_counts_as_no_gpus(self, monkeypatch):
        def explode():
            raise RuntimeError("CUDA driver version is insufficient")

        _fake_nvidia_smi(monkeypatch, found=False)
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=explode)),
        )
        assert pdf_text.gpu_count(docling=True) == 0

    def test_docling_regardless_of_config_parser(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        _fake_nvidia_smi(monkeypatch, n_gpus=2)
        assert pdf_text.gpu_count(docling=True) == 2


class TestVisibleDevices:
    def test_unset_means_every_device(self, monkeypatch):
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        assert pdf_text._visible_devices(4) == 4

    def test_a_single_device_narrows_the_count_to_one(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2")
        assert pdf_text._visible_devices(4) == 1

    def test_a_subset_is_counted_not_maxed(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,2")
        assert pdf_text._visible_devices(4) == 2

    def test_empty_means_no_devices_at_all(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
        assert pdf_text._visible_devices(4) == 0

    def test_minus_one_means_no_devices(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "-1")
        assert pdf_text._visible_devices(4) == 0

    def test_enumeration_stops_at_the_first_invalid_entry(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,nonsense,1")
        assert pdf_text._visible_devices(4) == 1

    def test_an_out_of_range_index_stops_enumeration(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,9")
        assert pdf_text._visible_devices(4) == 1

    def test_uuids_are_counted_as_devices(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-790508c0,GPU-d720f633")
        assert pdf_text._visible_devices(4) == 2

    def test_more_uuids_than_cards_is_clamped(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", ",".join(f"GPU-{i}" for i in range(6)))
        assert pdf_text._visible_devices(4) == 4

    def test_whitespace_around_entries_is_tolerated(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", " 0 , 1 ")
        assert pdf_text._visible_devices(4) == 2


def _fake_gpus(monkeypatch, free, listed=None, returncode=0, found=True, raises=None):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/nvidia-smi" if found else None)
    n_listed = len(free) if listed is None else listed

    def fake_run(cmd, **kwargs):
        if any("--query-gpu" in part for part in cmd):
            if raises is not None:
                raise raises
            body = "".join(f"{i}, {mib}\n" for i, mib in free.items())
            return subprocess.CompletedProcess(cmd, returncode, stdout=body, stderr="")
        body = "".join(f"GPU {i}: NVIDIA A40 (UUID: GPU-{i})\n" for i in range(n_listed))
        return subprocess.CompletedProcess(cmd, 0, stdout=body, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)


_FULL = 46068  # an A40, in MiB -- the card this was measured on
_ROOMY = 45000  # comfortably over _GPU_MIN_FREE_MIB
_CRAMPED = 600  # what the 44.4 GiB-occupied GPU 0 actually had left


class TestUsableDevices:
    @pytest.fixture(autouse=True)
    def _no_device_mask(self, monkeypatch):
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def test_no_gpus_means_no_devices_and_nothing_to_say(self):
        assert pdf_text.usable_devices(docling=False) == ([], None)

    def test_every_card_free_is_every_card_used(self, monkeypatch):
        _fake_gpus(monkeypatch, {i: _ROOMY for i in range(4)})
        assert pdf_text.usable_devices(docling=True) == ([0, 1, 2, 3], None)

    def test_a_full_card_is_skipped_and_named(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: _CRAMPED, 1: _ROOMY, 2: _ROOMY, 3: _ROOMY})
        devices, complaint = pdf_text.usable_devices(docling=True)
        assert devices == [1, 2, 3]
        assert "cuda:0 (0.6 GiB free)" in complaint
        assert "cuda:1,2,3" in complaint

    def test_a_card_exactly_at_the_threshold_is_kept(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: pdf_text._GPU_MIN_FREE_MIB, 1: _ROOMY})
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_a_card_one_MiB_short_is_skipped(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: pdf_text._GPU_MIN_FREE_MIB - 1, 1: _ROOMY})
        devices, complaint = pdf_text.usable_devices(docling=True)
        assert devices == [1]
        assert "cuda:0" in complaint

    def test_every_card_full_falls_back_to_the_cpu(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: _CRAMPED, 1: _CRAMPED})
        devices, complaint = pdf_text.usable_devices(docling=True)
        assert devices == []
        assert "every GPU is busy" in complaint
        assert "parsing on the CPU" in complaint

    def test_no_memory_reading_assumes_every_card_is_usable(self, monkeypatch):
        _fake_gpus(monkeypatch, {i: _ROOMY for i in range(2)}, returncode=9)
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_an_unreadable_card_is_assumed_usable(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: "[N/A]", 1: _ROOMY})
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_every_card_unreadable_is_no_reading_at_all(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: "[N/A]", 1: "[N/A]"})
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_a_card_nvidia_smi_did_not_report_on_is_kept(self, monkeypatch):
        _fake_gpus(monkeypatch, {0: _ROOMY, 1: _ROOMY, 2: _ROOMY}, listed=4)
        assert pdf_text.usable_devices(docling=True) == ([0, 1, 2, 3], None)

    def test_cuda_visible_devices_are_checked_by_physical_card(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3,1")
        _fake_gpus(monkeypatch, {0: _ROOMY, 1: _ROOMY, 2: _ROOMY, 3: _CRAMPED})
        devices, complaint = pdf_text.usable_devices(docling=True)
        assert devices == [1]
        assert "cuda:0" in complaint

    def test_a_uuid_device_list_is_not_filtered(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-abc,GPU-def")
        _fake_gpus(monkeypatch, {0: _CRAMPED, 1: _CRAMPED, 2: _ROOMY, 3: _ROOMY})
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_a_hanging_nvidia_smi_does_not_hang_the_sync(self, monkeypatch):
        _fake_gpus(
            monkeypatch,
            {0: _ROOMY, 1: _ROOMY},
            raises=subprocess.TimeoutExpired(["nvidia-smi"], 10),
        )
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_no_nvidia_smi_means_no_filtering(self, monkeypatch):
        _fake_gpus(monkeypatch, {}, found=False)
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda: 2)),
        )
        assert pdf_text.usable_devices(docling=True) == ([0, 1], None)

    def test_docling_regardless_of_config_parser(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        _fake_gpus(monkeypatch, {0: _CRAMPED, 1: _ROOMY})
        devices, complaint = pdf_text.usable_devices(docling=True)
        assert devices == [1]
        assert "cuda:0" in complaint


class TestParseVisibleDevices:
    def test_unset_maps_each_device_to_itself(self, monkeypatch):
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        assert pdf_text._parse_visible_devices(3) == (3, [0, 1, 2])

    def test_a_reordered_subset_keeps_its_order(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3,1")
        assert pdf_text._parse_visible_devices(4) == (2, [3, 1])

    def test_a_uuid_makes_the_mapping_unknowable(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,GPU-abc")
        assert pdf_text._parse_visible_devices(4) == (2, None)

    def test_enumeration_still_stops_at_the_first_invalid_entry(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2,nonsense,1")
        assert pdf_text._parse_visible_devices(4) == (1, [2])


class TestCudaOomRecovery:
    @pytest.fixture(autouse=True)
    def _reset(self):
        pdf_text._reset_worker_device()
        yield
        pdf_text._reset_worker_device()

    def test_recognises_the_driver_level_message(self):
        assert pdf_text.is_cuda_oom(RuntimeError("CUDA error: out of memory")) is True

    def test_recognises_the_torch_allocator_message(self):
        assert (
            pdf_text.is_cuda_oom(RuntimeError("CUDA out of memory. Tried to allocate 20.00 MiB"))
            is True
        )

    def test_an_ordinary_failure_is_not_an_oom(self):
        assert pdf_text.is_cuda_oom(RuntimeError("simulated docling failure")) is False

    def test_an_oom_falls_back_to_the_cpu_and_the_document_parses(
        self, isolated_config, fake_docling, tmp_path, capsys
    ):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [0, 1])
        out = pdf_text.extract_text(str(tmp_path / "cudaoom.pdf"), "key")
        assert "Parsed content" in out.read_text()
        assert pdf_text.worker_device() == "cpu"
        assert "fallen back" in capsys.readouterr().err

    def test_the_fallback_sticks_for_the_rest_of_the_run(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [0])
        pdf_text.extract_text(str(tmp_path / "cudaoom.pdf"), "one")
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "two")
        assert fake_docling.pipeline_options().accelerator_options.device == "cpu"

    def test_a_serial_run_falls_back_too(self, isolated_config, fake_docling, tmp_path):
        assert pdf_text.worker_device() is None
        out = pdf_text.extract_text(str(tmp_path / "cudaoom.pdf"), "key")
        assert "Parsed content" in out.read_text()
        assert pdf_text.worker_device() == "cpu"

    def test_an_oom_the_cpu_cannot_escape_is_reported_as_transient(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [0])
        with pytest.raises(pdf_text.ExtractionError) as caught:
            pdf_text.extract_text(str(tmp_path / "alwaysoom.pdf"), "key")
        assert getattr(caught.value, "transient", False) is True

    def test_an_ordinary_backend_failure_stays_deterministic(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [0])
        with pytest.raises(pdf_text.ExtractionError) as caught:
            pdf_text.extract_text(str(tmp_path / "explode.pdf"), "key")
        assert getattr(caught.value, "transient", False) is False


class TestCudaIsInitialised:
    def test_false_when_torch_was_never_imported(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "torch", raising=False)
        assert pdf_text.cuda_is_initialised() is False
        assert "torch" not in sys.modules

    def test_false_when_torch_is_imported_but_cuda_is_cold(self, monkeypatch):
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(is_initialized=lambda: False)),
        )
        assert pdf_text.cuda_is_initialised() is False

    def test_true_once_something_has_used_a_gpu(self, monkeypatch):
        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(is_initialized=lambda: True)),
        )
        assert pdf_text.cuda_is_initialised() is True

    def test_an_unanswerable_torch_is_assumed_initialised(self, monkeypatch):
        def explode():
            raise RuntimeError("no CUDA-capable device is detected")

        monkeypatch.setitem(
            sys.modules,
            "torch",
            types.SimpleNamespace(cuda=types.SimpleNamespace(is_initialized=explode)),
        )
        assert pdf_text.cuda_is_initialised() is True


class TestStartMethod:
    def test_auto_prefers_forkserver(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "auto")
        monkeypatch.setattr(
            multiprocessing, "get_all_start_methods", lambda: ["fork", "spawn", "forkserver"]
        )
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: False)
        assert pdf_text.start_method() == ("forkserver", None)

    def test_auto_falls_back_to_spawn_silently(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "auto")
        monkeypatch.setattr(multiprocessing, "get_all_start_methods", lambda: ["spawn"])
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: False)
        assert pdf_text.start_method() == ("spawn", None)

    def test_an_explicit_forkserver_that_cannot_be_honoured_says_so(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "forkserver")
        monkeypatch.setattr(multiprocessing, "get_all_start_methods", lambda: ["spawn"])
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: False)
        method, complaint = pdf_text.start_method()
        assert method == "spawn"
        assert "not available on this platform" in complaint

    def test_an_initialised_cuda_forces_spawn(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "auto")
        monkeypatch.setattr(
            multiprocessing, "get_all_start_methods", lambda: ["fork", "spawn", "forkserver"]
        )
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: True)
        method, complaint = pdf_text.start_method()
        assert method == "spawn"
        assert "CUDA is already initialised" in complaint

    def test_an_explicit_spawn_is_honoured_without_complaint(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "spawn")
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: False)
        assert pdf_text.start_method() == ("spawn", None)

    def test_spawn_does_not_need_the_cuda_check(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_START_METHOD", "spawn")
        monkeypatch.setattr(pdf_text._startup, "cuda_is_initialised", lambda: True)
        assert pdf_text.start_method() == ("spawn", None)

    def test_fork_is_not_a_configurable_value(self):
        assert "fork" not in config.PARSER_START_METHODS


class TestPreloadModules:
    def test_lists_the_modules_a_worker_would_import(self, monkeypatch):
        monkeypatch.setattr(
            importlib.util, "find_spec", lambda name: importlib.machinery.ModuleSpec(name, None)
        )
        assert pdf_text.preload_modules() == list(pdf_text._PRELOAD_MODULES)

    def test_drops_what_this_host_does_not_have(self, monkeypatch):
        monkeypatch.setattr(
            importlib.util,
            "find_spec",
            lambda name: None if name == "torch" else importlib.machinery.ModuleSpec(name, None),
        )
        assert "torch" not in pdf_text.preload_modules()

    def test_an_unimportable_parent_package_is_skipped_not_raised(self, monkeypatch):
        def explode(name):
            raise ModuleNotFoundError(f"No module named {name!r}")

        monkeypatch.setattr(importlib.util, "find_spec", explode)
        assert pdf_text.preload_modules() == []


@pytest.mark.skipif(
    "forkserver" not in multiprocessing.get_all_start_methods(),
    reason="no forkserver to prestart on this platform (Windows has spawn only)",
)
class TestPrestartPool:
    @pytest.fixture(autouse=True)
    def _a_machine_with_room(self, monkeypatch):
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)

    @pytest.fixture
    def started(self, monkeypatch):
        from multiprocessing import forkserver

        calls = []
        monkeypatch.setattr(forkserver, "ensure_running", lambda: calls.append("started"))
        monkeypatch.setattr(
            multiprocessing,
            "get_context",
            lambda method: types.SimpleNamespace(set_forkserver_preload=lambda names: None),
        )
        return calls

    def test_the_fixture_above_means_a_pool_really_is_coming(self):
        assert pdf_text.worker_ceiling(docling=True) > 1

    def test_starts_the_forkserver_when_a_pool_is_coming(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))

        pdf_text.prestart_pool()

        assert started == ["started"]

    def test_a_default_serial_run_starts_nothing(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 1)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))

        pdf_text.prestart_pool()

        assert started == []

    def test_auto_on_a_small_machine_starts_nothing(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 4)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))

        pdf_text.prestart_pool()

        assert pdf_text.worker_ceiling(docling=True) == 1
        assert started == []

    def test_auto_on_a_large_machine_does_start(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", "auto")
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 48)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))

        pdf_text.prestart_pool()

        assert started == ["started"]

    def test_an_explicit_count_above_a_ceiling_of_one_starts_nothing(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 8)
        monkeypatch.setattr(pdf_text._sizing, "allowed_cpus", lambda: 4)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))

        pdf_text.prestart_pool()

        assert pdf_text.resolve_workers(100, docling=True)[0] == 1
        assert started == []

    def test_the_pdftotext_backend_starts_nothing(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)

        pdf_text.prestart_pool()

        assert started == []

    def test_nothing_is_started_when_spawn_was_chosen(self, monkeypatch, started):
        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("spawn", None))

        pdf_text.prestart_pool()

        assert started == []

    def test_a_failure_to_prestart_is_swallowed(self, monkeypatch):
        from multiprocessing import forkserver

        monkeypatch.setattr(config, "PARSER", "docling")
        monkeypatch.setattr(config, "PARSER_WORKERS", 4)
        monkeypatch.setattr(pdf_text._startup, "start_method", lambda: ("forkserver", None))
        monkeypatch.setattr(
            multiprocessing,
            "get_context",
            lambda method: types.SimpleNamespace(set_forkserver_preload=lambda names: None),
        )

        def explode():
            raise OSError("fork: resource temporarily unavailable")

        monkeypatch.setattr(forkserver, "ensure_running", explode)

        pdf_text.prestart_pool()  # must not raise


class TestProcessPoolContext:
    def test_the_forkserver_is_told_what_to_preload(self, monkeypatch):
        recorded = []

        class FakeContext:
            def set_forkserver_preload(self, names):
                recorded.append(names)

        monkeypatch.setattr(pdf_text._pool, "start_method", lambda: ("forkserver", None))
        monkeypatch.setattr(multiprocessing, "get_context", lambda method: FakeContext())
        monkeypatch.setattr(pdf_text._pool, "preload_modules", lambda: ["torch"])

        ctx, complaint = pdf_text.process_pool_context()

        assert recorded == [["torch"]]
        assert complaint is None

    def test_spawn_gets_no_preload_list(self, monkeypatch):
        class FakeContext:
            def set_forkserver_preload(self, names):
                raise AssertionError("spawn has no forkserver to preload")

        monkeypatch.setattr(pdf_text._pool, "start_method", lambda: ("spawn", "  NOTE why"))
        monkeypatch.setattr(multiprocessing, "get_context", lambda method: FakeContext())

        ctx, complaint = pdf_text.process_pool_context()

        assert complaint == "  NOTE why"


class TestWorkerDevice:
    @pytest.fixture(autouse=True)
    def _reset(self):
        pdf_text._reset_worker_device()
        yield
        pdf_text._reset_worker_device()

    def test_workers_are_assigned_round_robin(self):
        counter, lock = _FakeCounter(), _FakeLock()
        seen = []
        for _ in range(6):
            pdf_text.init_worker(counter, lock, [0, 1, 2, 3])
            seen.append(pdf_text._worker._WORKER_DEVICE)
        assert seen == ["cuda:0", "cuda:1", "cuda:2", "cuda:3", "cuda:0", "cuda:1"]

    def test_the_round_robin_walks_only_the_usable_cards(self):
        counter, lock = _FakeCounter(), _FakeLock()
        seen = []
        for _ in range(4):
            pdf_text.init_worker(counter, lock, [1, 2, 4])
            seen.append(pdf_text._worker._WORKER_DEVICE)
        assert seen == ["cuda:1", "cuda:2", "cuda:4", "cuda:1"]

    def test_no_gpus_means_no_device_override(self):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [])
        assert pdf_text._worker._WORKER_DEVICE is None

    def test_the_assigned_device_reaches_the_pipeline(
        self, isolated_config, fake_docling, tmp_path
    ):
        pdf_text.init_worker(_FakeCounter(), _FakeLock(), [0, 1, 2, 3])
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a", threads=2)
        opts = fake_docling.pipeline_options().accelerator_options
        assert opts.device == "cuda:0"
        assert opts.num_threads == 2

    def test_device_is_part_of_the_converter_cache_key(
        self, isolated_config, fake_docling, tmp_path
    ):
        counter, lock = _FakeCounter(), _FakeLock()
        pdf_text.init_worker(counter, lock, [0, 1, 2, 3])
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        pdf_text.init_worker(counter, lock, [0, 1, 2, 3])
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "b")
        assert fake_docling.build_count == 2
        assert fake_docling.pipeline_options().accelerator_options.device == "cuda:1"


class _FakeCounter:
    def __init__(self):
        self.value = 0


class _FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class TestDoclingPartialSuccess:
    def test_partial_success_is_rejected(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            fake_docling,
            "convert",
            lambda self, p: _FakeResult("PARTIAL_SUCCESS", ["timeout after 10s"]),
            raising=False,
        )
        with pytest.raises(pdf_text.ExtractionError, match="PARTIAL_SUCCESS"):
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")

    def test_the_reason_docling_gave_is_carried_through(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            fake_docling,
            "convert",
            lambda self, p: _FakeResult("PARTIAL_SUCCESS", ["Document processing timeout"]),
            raising=False,
        )
        with pytest.raises(pdf_text.ExtractionError, match="timeout"):
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")

    def test_no_file_is_written_for_a_partial_parse(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            fake_docling,
            "convert",
            lambda self, p: _FakeResult("PARTIAL_SUCCESS", []),
            raising=False,
        )
        with pytest.raises(pdf_text.ExtractionError):
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert not (isolated_config.PARSED_DIR / "a.txt").exists()

    def test_success_passes_through(self, isolated_config, fake_docling, tmp_path):
        out = pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert out.read_text().startswith("# Parsed content")

    def test_a_result_without_a_status_attribute_is_refused(self):
        with pytest.raises(pdf_text.ExtractionError) as raised:
            pdf_text.check_docling_status(types.SimpleNamespace())
        assert "no `status` attribute" in str(raised.value)


class _FakeResult:
    def __init__(self, status_name, messages, categories=None):
        self.status = types.SimpleNamespace(name=status_name)
        cats = categories if categories is not None else [None] * len(messages)
        self.errors = [
            types.SimpleNamespace(error_message=m)
            if c is None
            else types.SimpleNamespace(error_message=m, category=c)
            for m, c in zip(messages, cats, strict=True)
        ]
        self.document = FakeDoclingDocument("# partial")


class _FakeProcess:
    def __init__(self, alive_after_terminate=False, raises=None):
        self.terminated = False
        self.killed = False
        self.joined = None
        self._alive = alive_after_terminate
        self._raises = raises

    def terminate(self):
        if self._raises:
            raise self._raises
        self.terminated = True

    def join(self, timeout=None):
        self.joined = timeout

    def is_alive(self):
        return self._alive

    def kill(self):
        self.killed = True
        self._alive = False


class TestTerminateWorkers:
    def test_workers_are_asked_to_stop(self):
        procs = {0: _FakeProcess(), 1: _FakeProcess()}
        pdf_text.terminate_workers(types.SimpleNamespace(_processes=procs))
        assert all(p.terminated for p in procs.values())
        assert not any(p.killed for p in procs.values())

    def test_a_worker_ignoring_sigterm_is_killed(self):
        stubborn = _FakeProcess(alive_after_terminate=True)
        pdf_text.terminate_workers(types.SimpleNamespace(_processes={0: stubborn}))
        assert stubborn.terminated
        assert stubborn.killed
        assert stubborn.joined == pdf_text._TERMINATE_GRACE_SECONDS

    def test_an_already_reaped_worker_is_not_an_error(self):
        gone = _FakeProcess(raises=ProcessLookupError("no such process"))
        pdf_text.terminate_workers(types.SimpleNamespace(_processes={0: gone}))

    def test_a_worker_that_dies_between_terminate_and_join_is_not_an_error(self):
        class VanishingProcess(_FakeProcess):
            def join(self, timeout=None):
                raise ProcessLookupError("reaped between terminate and join")

        vanishing = VanishingProcess()
        pdf_text.terminate_workers(types.SimpleNamespace(_processes={0: vanishing}))
        assert vanishing.terminated

    def test_a_thread_pool_has_nothing_to_terminate(self):
        pdf_text.terminate_workers(types.SimpleNamespace())

    def test_an_already_shut_down_pool_has_nothing_to_terminate(self):
        pdf_text.terminate_workers(types.SimpleNamespace(_processes=None))


class TestInterruptGuard:
    def test_it_installs_and_restores_the_handler(self):
        before = signal.getsignal(signal.SIGINT)
        with pdf_text.interrupt_guard(types.SimpleNamespace(), lambda: "0/0"):
            assert signal.getsignal(signal.SIGINT) is not before
        assert signal.getsignal(signal.SIGINT) is before

    def test_off_the_main_thread_it_degrades_instead_of_raising(self, monkeypatch):
        def refuse(*args):
            raise ValueError("signal only works in main thread")

        monkeypatch.setattr(pdf_text._interrupt.signal, "signal", refuse)
        with pdf_text.interrupt_guard(types.SimpleNamespace(), lambda: "0/0") as guard:
            assert guard._previous is None

    def test_the_handler_reports_progress_terminates_and_exits(self, monkeypatch, capsys):
        procs = {0: _FakeProcess()}
        exits = []
        monkeypatch.setattr(pdf_text._interrupt.os, "_exit", lambda code: exits.append(code))

        guard = pdf_text.interrupt_guard(
            types.SimpleNamespace(_processes=procs), lambda: "7/24 document(s) parsed"
        )
        guard._on_sigint(signal.SIGINT, None)

        err = capsys.readouterr().err
        assert "7/24" in err
        assert "re-run to continue" in err
        assert procs[0].terminated
        assert exits == [130]


class TestDocumentTimeout:
    def test_pdftotext_gets_a_subprocess_timeout(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 30.0)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert captured["timeout"] == 30.0

    def test_pdftotext_without_a_timeout_waits_forever(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", None)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", fake_run)
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert captured["timeout"] is None

    def test_a_timed_out_pdftotext_is_an_extraction_error(
        self, isolated_config, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 5.0)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 5.0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(pdf_text.ExtractionError, match="5.0s"):
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")

    def test_docling_gets_its_own_document_timeout(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 120.0)
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert fake_docling.pipeline_options().document_timeout == 120.0

    def test_docling_timeout_is_part_of_the_converter_cache_key(
        self, isolated_config, fake_docling, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 120.0)
        pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 60.0)
        pdf_text.extract_text(str(tmp_path / "b.pdf"), "b")
        assert fake_docling.build_count == 2


class TestTimeoutIsRecordedAsSuch:
    def test_a_timed_out_pdftotext_says_it_timed_out(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER_DOCUMENT_TIMEOUT", 5.0)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 5.0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert excinfo.value.timed_out is True

    def test_an_unreadable_pdf_does_not(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr=b"Syntax Error: Couldn't read xref")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.extract_text(str(tmp_path / "a.pdf"), "a")
        assert getattr(excinfo.value, "timed_out", False) is False

    def test_docling_says_so_from_its_own_failure_category(self):
        result = _FakeResult(
            "PARTIAL_SUCCESS", ["something upstream reworded"], categories=["timeout"]
        )
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert excinfo.value.timed_out is True

    def test_a_str_enum_category_is_read_by_value(self):
        class FailureCategory(str, enum.Enum):
            TIMEOUT = "timeout"

        result = _FakeResult(
            "PARTIAL_SUCCESS", ["ran out of time"], categories=[FailureCategory.TIMEOUT]
        )
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert excinfo.value.timed_out is True

    def test_a_bad_page_is_not_a_timeout(self):
        result = _FakeResult(
            "PARTIAL_SUCCESS", ["page 3 could not be decoded"], categories=["backend_failure"]
        )
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert excinfo.value.timed_out is False

    @pytest.mark.parametrize(
        "message",
        [
            "document timeout exceeded",  # threaded pipeline
            "Document processing timeout: exceeded 10.000s limit after "  # page-batch loop
            "12.345s. Processed 3/17 pages.",
        ],
    )
    def test_the_wording_is_the_fallback_when_there_is_no_category(self, message):
        result = _FakeResult("PARTIAL_SUCCESS", [message])
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert excinfo.value.timed_out is True

    def test_an_unrelated_timeout_is_not_this_timeout(self):
        result = _FakeResult("PARTIAL_SUCCESS", ["connection timeout fetching model weights"])
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert excinfo.value.timed_out is False

    def test_a_timeout_past_the_display_cap_is_still_found(self):
        result = _FakeResult(
            "PARTIAL_SUCCESS",
            [f"page {i} was skipped" for i in range(20)] + ["out of time"],
            categories=["backend_failure"] * 20 + ["timeout"],
        )
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert "out of time" not in str(excinfo.value)  # capped, as before
        assert excinfo.value.timed_out is True

    def test_the_mark_survives_the_trip_back_from_a_worker(self):
        error = pdf_text.ExtractionError("out of time")
        error.timed_out = True
        revived = pickle.loads(pickle.dumps(error))
        assert revived.timed_out is True


class TestDoclingErrorMessage:
    def test_repeated_reasons_are_collapsed(self):
        result = _FakeResult("PARTIAL_SUCCESS", ["document timeout exceeded"] * 675)
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        assert str(excinfo.value).count("document timeout exceeded") == 1

    def test_distinct_reasons_are_kept_and_the_rest_counted(self):
        result = _FakeResult("PARTIAL_SUCCESS", [f"reason {i}" for i in range(10)])
        with pytest.raises(pdf_text.ExtractionError) as excinfo:
            pdf_text.check_docling_status(result)
        message = str(excinfo.value)
        assert "reason 0" in message
        assert "reason 2" in message
        assert "(+7 more)" in message


class TestBackendChatterCarriesTheCitekey:
    @pytest.fixture
    def _fake_backend(self, isolated_config, monkeypatch, tmp_path):
        monkeypatch.setattr(pdf_text, "is_available", lambda: True)
        monkeypatch.setattr(config, "PARSER", "docling")
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        def run(chatter, citekey="lin_utwin_2023"):
            def extractor(pdf_path, out_path, threads):
                chatter()
                out_path.write_text("text", encoding="utf-8")
                return None

            monkeypatch.setitem(pdf_text._EXTRACTORS, "docling", extractor)
            return pdf_text.extract_text(str(pdf), citekey)

        return run

    def test_a_bare_print_from_the_backend_is_prefixed(self, _fake_backend, capsys):
        _fake_backend(lambda: print("RapidOCR returned empty result!"))
        assert capsys.readouterr().out == "[lin_utwin_2023] RapidOCR returned empty result!\n"

    def test_stderr_is_prefixed_too(self, _fake_backend, capsys):
        _fake_backend(lambda: print("empty page", file=sys.stderr))
        assert capsys.readouterr().err == "[lin_utwin_2023] empty page\n"

    def test_every_line_of_a_multi_line_write_is_prefixed(self, _fake_backend, capsys):
        _fake_backend(lambda: print("first\nsecond"))
        out = capsys.readouterr().out
        assert out == "[lin_utwin_2023] first\n[lin_utwin_2023] second\n"

    def test_a_line_built_across_several_writes_is_prefixed_once(self, _fake_backend, capsys):
        def chatter():
            print("loading ", end="")
            print("models", end="")
            print(" done")

        _fake_backend(chatter)
        assert capsys.readouterr().out == "[lin_utwin_2023] loading models done\n"

    @pytest.fixture
    def _foreign_logger(self, monkeypatch, request):
        buffer = io.StringIO()
        logger = logging.getLogger(f"FakeOCR.{request.node.name}")
        logger.propagate = False
        logger.setLevel(logging.WARNING)

        def redirect():
            monkeypatch.setattr(sys, "stderr", buffer)
            return buffer

        try:
            yield logger, redirect
        finally:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)

    def test_a_log_handler_built_during_the_parse_is_annotated(
        self, _fake_backend, _foreign_logger
    ):
        logger, redirect = _foreign_logger
        buffer = redirect()

        def chatter():
            logger.addHandler(logging.StreamHandler(sys.stderr))
            logger.warning("The text detection result is empty")

        _fake_backend(chatter)
        assert buffer.getvalue() == "[lin_utwin_2023] The text detection result is empty\n"

    def test_the_citekey_is_never_printed_twice_on_one_line(self, _fake_backend, _foreign_logger):
        logger, redirect = _foreign_logger
        buffer = redirect()

        def chatter():
            logger.addHandler(logging.StreamHandler(sys.stderr))
            logger.warning("empty result")

        _fake_backend(chatter)
        assert buffer.getvalue().count("[lin_utwin_2023]") == 1

    def test_a_captured_stream_keeps_up_with_the_citekey(self, _fake_backend, _foreign_logger):
        logger, redirect = _foreign_logger
        buffer = redirect()
        _fake_backend(
            lambda: logger.addHandler(logging.StreamHandler(sys.stderr)),
            citekey="doc_a",
        )
        _fake_backend(lambda: logger.warning("later chatter"), citekey="doc_b")
        assert buffer.getvalue() == "[doc_b] later chatter\n"

    def test_a_handler_bound_before_any_parse_is_left_alone(self, _fake_backend, _foreign_logger):
        logger, redirect = _foreign_logger
        buffer = redirect()
        logger.addHandler(logging.StreamHandler(sys.stderr))
        _fake_backend(lambda: logger.warning("a message of ours"))
        assert buffer.getvalue() == "a message of ours\n"

    def test_nothing_is_annotated_outside_the_backend_call(self, _fake_backend, capsys):
        _fake_backend(lambda: None)
        print("a line sync printed after the parse")
        assert capsys.readouterr().out == "a line sync printed after the parse\n"

    def test_a_progress_bar_redraw_is_prefixed_each_time(self, _fake_backend, capsys):
        def chatter():
            sys.stderr.write("loading:  0%\rloading: 50%\rloading: 100%\n")

        _fake_backend(chatter)
        assert capsys.readouterr().err == (
            "[lin_utwin_2023] loading:  0%\r"
            "[lin_utwin_2023] loading: 50%\r"
            "[lin_utwin_2023] loading: 100%\n"
        )

    def test_the_streams_are_restored_when_the_backend_raises(self, _fake_backend, capsys):
        def chatter():
            raise pdf_text.ExtractionError("unreadable")

        with pytest.raises(pdf_text.ExtractionError):
            _fake_backend(chatter)
        print("after the failure")
        assert capsys.readouterr().out == "after the failure\n"


class TestAnnotatedOutputOnItsOwn:
    def test_it_nests_without_doubling_the_prefix(self, capsys):
        with pdf_text.annotated_output("outer"):
            with pdf_text.annotated_output("inner"):
                print("innermost")
            print("back outside")
        assert capsys.readouterr().out == ("[inner] innermost\n[outer] back outside\n")

    def test_it_writes_through_untouched_outside_any_document(self, capsys):
        with pdf_text.annotated_output("k"):
            captured = sys.stdout
        captured.write("between documents\n")
        assert capsys.readouterr().out == "between documents\n"

    def test_it_delegates_unknown_attributes_to_the_real_stream(self, monkeypatch):
        class Stub(io.StringIO):
            def isatty(self):
                return True

        stub = Stub()
        monkeypatch.setattr(sys, "stdout", stub)
        with pdf_text.annotated_output("k"):
            assert sys.stdout.isatty() is True
            sys.stdout.write("a line\n")
            sys.stdout.flush()
        assert stub.getvalue() == "[k] a line\n"
        assert sys.stdout is stub

    def test_write_reports_the_length_it_was_given(self):
        with pdf_text.annotated_output("k"):
            assert sys.stdout.write("four") == 4


def test_the_docling_hint_names_each_shape_its_own_command():
    from chitragupta import pdf_text

    hint = pdf_text._INSTALL_HINT["docling"]
    assert "in a git checkout, `bash scripts/install_full_pipeline.sh python-deps`" in hint
    assert "in an installed project, `chitragupta install enrich`" in hint
