"""`annotated_output` under the pdftotext thread pool (#960).

With `[parser].workers > 1` and the pdftotext backend, `sync_pool` runs
`extract_one` on a `ThreadPoolExecutor`, so several documents are inside
`annotated_output` at once in one process. Kept apart from
`tests/test_pdf_text.py`'s single-threaded cases because every test here
needs two real threads and barriers forcing one interleaving.
"""

import sys
import threading

from chitragupta import pdf_text


def _interleaved(say_a, say_b) -> None:
    """Run two documents on two threads in the order A enters, B enters,
    A exits, B exits: the order that left `sys.stdout` wearing A's
    wrapper. `say_a`/`say_b` run while both documents are open."""
    both_in = threading.Barrier(3)
    a_out = threading.Event()
    spoke = threading.Barrier(3)

    def document_a():
        with pdf_text.annotated_output("doc_a"):
            both_in.wait()
            say_a()
            spoke.wait()
        a_out.set()

    def document_b():
        with pdf_text.annotated_output("doc_b"):
            both_in.wait()
            say_b()
            spoke.wait()
            a_out.wait()

    threads = [threading.Thread(target=document_a), threading.Thread(target=document_b)]
    for thread in threads:
        thread.start()
    both_in.wait()
    print("sync's own line, mid-run")
    spoke.wait()
    for thread in threads:
        thread.join()


class TestTwoDocumentsAtOnce:
    def test_the_streams_are_the_originals_afterwards(self, capsys):
        """The reproduced bug: after A-enter, B-enter, A-exit, B-exit,
        B restored what *it* found, which was A's wrapper, and every
        later line of `sync`'s stdout carried `[doc_a]`."""
        original_out, original_err = sys.stdout, sys.stderr
        _interleaved(lambda: None, lambda: None)
        assert sys.stdout is original_out
        assert sys.stderr is original_err
        print("Sync complete: 2 parsed")
        assert capsys.readouterr().out.endswith("\nSync complete: 2 parsed\n")

    def test_each_thread_is_labelled_with_its_own_citekey(self, capsys):
        """One process-global citekey labelled both threads' output
        with whichever document entered last."""
        _interleaved(lambda: print("from a"), lambda: print("from b"))
        lines = capsys.readouterr().out.splitlines()
        assert "[doc_a] from a" in lines
        assert "[doc_b] from b" in lines

    def test_the_main_thread_is_never_labelled_while_workers_parse(self, capsys):
        """`sync` prints its own contract lines from the main thread
        while pool threads are mid-document. Those lines name no
        document, so they must not borrow a worker's citekey."""
        _interleaved(lambda: None, lambda: None)
        assert "sync's own line, mid-run" in capsys.readouterr().out.splitlines()


def _from_a_new_thread(text: str) -> None:
    """Print `text` from a thread the backend started itself, the way
    docling's `StandardPdfPipeline` runs its OCR stage."""
    thread = threading.Thread(target=lambda: print(text))
    thread.start()
    thread.join()


class TestABackendsOwnThreads:
    """A new thread starts with an empty context, so it cannot see the
    citekey of the document that started it. Docling runs each pipeline
    stage, OCR included, in a thread of its own, and RapidOCR's
    unattributed complaints -- the reason #154 exists -- are printed
    from there."""

    def test_a_thread_started_inside_the_only_open_document_is_labelled(self, capsys):
        with pdf_text.annotated_output("doc_a"):
            _from_a_new_thread("RapidOCR returned empty result!")
        assert capsys.readouterr().out == "[doc_a] RapidOCR returned empty result!\n"

    def test_with_two_documents_open_a_stray_thread_is_left_unlabelled(self, capsys):
        """Two in flight, so which one a context-less thread belongs to
        is unknowable; naming either would be the guess #154 removed."""
        _interleaved(lambda: _from_a_new_thread("whose is this?"), lambda: None)
        assert "whose is this?" in capsys.readouterr().out.splitlines()

    def test_the_main_thread_never_borrows_the_only_open_document(self, capsys):
        """With one pool thread mid-document, sync's own lines from the
        main thread still carry no citekey."""
        entered, release = threading.Event(), threading.Event()

        def document():
            with pdf_text.annotated_output("doc_a"):
                entered.set()
                release.wait()

        worker = threading.Thread(target=document)
        worker.start()
        entered.wait()
        print("  parsed  doc_b")
        release.set()
        worker.join()
        assert capsys.readouterr().out == "  parsed  doc_b\n"
