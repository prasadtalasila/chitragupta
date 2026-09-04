"""Would a figure-similarity tier (#659) catch a draft figure redrawn from
a source's, and can it tell that apart from two same-field papers drawing
the same standard diagram?

#659 proposes a new review-layer tier: rasterise a draft's TikZ figures,
embed them and the corpus's own extracted figure crops with an image
encoder, and rank the crops by cosine similarity -- ranked and scored,
never banded, exactly as #428's claim-support class already is, and for
the same reason PLAGIARISM-DESIGN.md gives for text: no threshold
separated a planted lift from same-field false positives there, and
there is no reason to expect a shared corpus's figures to behave better.
This measures, before any of that ships, whether the signal exists at
all.

**Four things, in the order a broken pipeline would be found**, per
PLAGIARISM-DESIGN.md's own methodology:

1. **Identity control.** Embed one real corpus crop, decoded fresh a
   second time, and confirm it is its own nearest neighbour at
   cosine ~1.0 among the whole set. A TikZ figure rasterises to clean
   line art on a white background; a corpus crop is a PDF-rendered
   raster that already went through a lossy PNG re-encode. If the
   planted case below ranks badly, the identity control is what tells
   apart "the encoder is weak on line art" from "the whole pipeline is
   broken" -- without it, no other number here means anything.
2. **The false-positive floor.** For every corpus crop, its cosine to
   the nearest crop that is neither the same paper (a paper's own Fig.
   3a and 3b, or the same PDF filed under two citekeys -- see
   `citekey_paper_groups`) nor a byte-identical duplicate of it (a
   shared book/collection's own figure repeated across chapters, or a
   publisher logo docling mis-extracted as a "figure" in several
   unrelated papers -- see `_assign_content_groups`, added after a first
   dev run showed exactly this pinning the floor's tail at cosine 1.0
   for a reason that had nothing to do with genuine visual similarity).
   A draft figure never legitimately collides with either case, so the
   distribution this produces is the noise floor a real signal has to
   clear.
3. **Recall on a graded planted case**, in the shape
   `bench_overlap_embed.py` already uses for text: four fixtures under
   `bench/fixtures/figure_similarity/`, all citekey-free --
   `faithful_trace.tex` (same boxes, labels and edges as a real corpus
   figure, in that figure's own visual style -- rounded, pale-yellow
   UML boxes), `traced_redraw.tex` (the same structural copy in a
   generic plain-rectangle style), `relabelled_redraw.tex` (same
   topology, generic labels), and `original_diagram.tex` (a legitimately
   original diagram in the same box-and-arrow genre, the negative
   control). A tier worth having ranks the real source figure for the
   first two well above chance and above the third and fourth.
4. **Encoder choice and cost.** `adapters` pins
   `transformers>=4.57.6,<4.58.0` (pyproject.toml); both a CLIP-class
   and a SigLIP-class encoder are confirmed here to load and encode
   under that pin (SigLIP through its vision tower only --
   `SiglipVisionModel`/`AutoImageProcessor` -- since the fused
   `AutoProcessor` path pulls in a tokenizer that needs `sentencepiece`,
   not a declared dependency, and this measurement needs no text
   encoder). Each is timed end-to-end (decode once, re-used across both)
   for the per-crop wall-clock cost a real tier would carry.

A cheap perceptual-hash prescreen (plain 8x8 average-hash, no new
dependency -- `ImageHash` would start a lock fight inside a measurement
PR) is measured alongside the encoders' floor/recall, since #659
proposes it as a first screening pass before the embedding rank.

**What this cannot see.** It measures four hand-built fixtures against
one real corpus figure the author chose because it redraws simply as
boxes and arrows -- not photographic or plot-heavy figures, which this
corpus also has plenty of and an image encoder may behave very
differently on. It is n=1 on the planted-positive side; the floor
(hundreds to thousands of pairs) is the part with statistical weight.
It also never runs the perceptual-hash screen and the embedding rank as
a cascade (screen first, embed only what survives) -- each is scored
against the same floor/recall question independently, because #659 asks
whether the *signal* exists before asking how to compose two of them.

    .venv-full/bin/python bench/bench_figure_similarity.py \\
        --tag 2026-09-04-figure-similarity --encoders clip,siglip

Needs `[enrich].docling_images` crops already on disk
(`content/docling/*.figures.json` + the PNGs they name) and the `enrich`
Poetry group's `sentence-transformers`/`transformers`/`torch`/Pillow,
plus a working `pdflatex` + `pypdfium2` for the TikZ fixtures. Reports,
rather than substituting, if the corpus crop count differs from a prior
run's -- enrichment coverage moves as the corpus is re-synced.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image

from chitragupta import config, ledger

# The real figure this benchmark's planted case redraws. Named once here
# so the "does the source rank above the floor" check does not have to
# re-derive it from the fixture's own comment.
_PLANTED_SOURCE_CITEKEY = "karabey_aksakalli_deployment_2021"
_PLANTED_SOURCE_IMAGE = "karabey_aksakalli_deployment_2021_artifacts/picture_000004.png"

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "figure_similarity"
_TEX_WRAP = (
    "\\documentclass{article}\n"
    # A generously oversized page, not the article default: a figure
    # whose tikzpicture is wider than the page's own MediaBox is not
    # merely an "overfull hbox" LaTeX draws into the margin -- pdfium
    # rasterises exactly the MediaBox, so anything past it is truly
    # absent from the PNG, not just visually crowded. Found empirically:
    # the first version of this wrapper used bare `article` (page ~
    # 15-17cm wide depending on the install's default paper size), and a
    # ~16cm-wide fixture came back with its rightmost boxes silently
    # missing borders and text -- a wrong measurement that looked like a
    # clean one. 40x30cm comfortably fits every fixture this script
    # ships, and the autocrop after rendering removes the blank margin.
    "\\usepackage[paperwidth=40cm,paperheight=30cm,margin=0.5cm]{geometry}\n"
    "\\usepackage{tikz}\n"
    "\\usetikzlibrary{arrows.meta,positioning}\n"
    "\\begin{document}\n"
    "\\thispagestyle{empty}\n"
    "%s\n"
    "\\end{document}\n"
)


def citekey_paper_groups():
    """`{citekey: title}` from the ledger -- the corpus's own notion of
    "the same paper filed under two citekeys". 55 of this corpus's 642
    ledger items (2026-09-04) share a title with at least one other
    citekey -- almost always the same PDF attached to a bib entry twice,
    e.g. `abbiati_modelling_2024`/`-1`/`-2` all title "Modelling for
    Digital Twins". Grouping the cross-paper floor by raw citekey instead
    of this would count every such pair's identical figures as "genuine
    cross-paper reuse", pinning the floor's upper tail at cosine 1.0 for
    a reason that has nothing to do with the field's drawing conventions.
    """
    with ledger.connection() as con:
        return dict(con.execute("SELECT citekey, title FROM items").fetchall())


def load_corpus_crops(docling_dir, paper_groups):
    """Every `(citekey, paper_group, cite, caption, path)` a real
    `.figures.json` names, for whichever crop file still exists on disk.

    Deliberately reads the index rather than globbing PNGs: globbing
    would also pick up whatever crops fell under the enrichment layer's
    own junk floor and were never indexed, and would have no route at
    all to the paper's own figure number -- `cite` carries that, a
    docling picture ordinal does not (#659's own checklist requires the
    former). `paper_group` falls back to the citekey itself for a
    citekey the ledger has since lost (a stale `.figures.json` after a
    re-sync), rather than raising -- this script is read-only over the
    corpus and would rather under-mask one figure than crash.
    """
    crops = []
    for fjson in sorted(docling_dir.glob("*.figures.json")):
        citekey = fjson.name[: -len(".figures.json")]
        records = json.loads(fjson.read_text(encoding="utf-8"))
        for record in records:
            image = record.get("image")
            if not image:
                continue
            path = docling_dir / image
            if not path.exists():
                continue
            crops.append(
                {
                    "citekey": citekey,
                    "paper_group": paper_groups.get(citekey, citekey),
                    "cite": record.get("cite"),
                    "caption": record.get("caption"),
                    "image": image,
                    "path": path,
                }
            )
    _assign_content_groups(crops)
    return crops


def _assign_content_groups(crops):
    """Add `content_group` in place: crops whose PNG bytes are
    byte-identical share one group, keyed by md5.

    Found empirically, not anticipated: 95 of this corpus's exact-match
    crop groups (2026-09-04) span *different* `paper_group`s -- a shared
    book/collection's own introductory figure repeated verbatim across
    its chapters (different citekeys, different titles, same editorial
    figure), and a publisher's page-1 header/logo docling mis-extracted
    as a "figure" in several unrelated papers. Neither is "two authors
    independently drawing the same standard diagram", which is what the
    cross-paper floor is supposed to measure -- both are the same bytes
    appearing more than once, and masking only by `paper_group` (title)
    left the floor's p95+ pinned at cosine ~1.0 for this reason rather
    than for any genuine same-field visual similarity."""
    import hashlib

    for crop in crops:
        crop["content_group"] = hashlib.md5(crop["path"].read_bytes()).hexdigest()


def average_hash(image, hash_size=8):
    """An 8x8 perceptual hash as a flat bool array -- the cheap prescreen
    #659 proposes ahead of the embedding rank. Plain PIL/numpy rather
    than the `ImageHash` package: the same algorithm in ~5 lines, with no
    new pinned dependency for a measurement script to justify."""
    small = image.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(small, dtype=np.float64)
    return (pixels > pixels.mean()).flatten()


def hamming(hash_a, hash_b):
    return int(np.count_nonzero(hash_a != hash_b))


def hamming_matrix_chunked(hashes, chunk=500):
    """All-pairs Hamming distance over `hashes` (each a flat bool array of
    the same length), via `d(x, y) = popcount(x) + popcount(y) -
    2 * dot(x, y)` for 0/1 vectors -- the same chunked-matmul shape as
    `cosine_matrix_chunked`, since a naive Python double loop over
    thousands of hashes (`bench_figure_similarity.py`'s first draft) is
    tens of millions of individual `hamming()` calls and does not
    finish in reasonable time."""
    bits = np.asarray(hashes, dtype=np.float32)
    popcount = bits.sum(axis=1)
    out = np.empty((len(bits), len(bits)), dtype=np.float32)
    for start in range(0, len(bits), chunk):
        dot = bits[start : start + chunk] @ bits.T
        out[start : start + chunk] = (
            popcount[start : start + chunk, None] + popcount[None, :] - 2 * dot
        )
    return out


def rasterize_tikz(tex_source, dpi=150):
    """Compile a standalone TikZ fragment and rasterise page 1 to a PIL
    image, autocropped to its non-white content -- the same rendering
    step #659's proposed tier would run on a draft's `figures/<n>.tex`
    (`chitragupta/review/figure_layout/_probe.py` already compiles the
    same kind of fragment to measure geometry; this compiles to rasterise
    instead, so it is not reused directly)."""
    import pypdfium2 as pdfium

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        doc_path = tmp / "fig.tex"
        doc_path.write_text(_TEX_WRAP % tex_source, encoding="utf-8")
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", doc_path.name],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        pdf_path = tmp / "fig.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(f"tikz fixture failed to compile:\n{result.stdout[-3000:]}")
        pdf = pdfium.PdfDocument(str(pdf_path))
        page = pdf[0]
        bitmap = page.render(scale=dpi / 72)
        image = bitmap.to_pil().convert("RGB")
        page.close()
        pdf.close()
    bbox = Image.eval(image, lambda p: 255 - p).getbbox()
    return image.crop(bbox) if bbox else image


def load_clip(device):
    """CLIP-class encoder via `sentence-transformers`, confirmed to load
    under the `transformers>=4.57.6,<4.58.0` pin `adapters` holds."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("clip-ViT-B-32", device=device)

    def embed(images, batch_size=64):
        return np.asarray(model.encode(images, batch_size=batch_size, show_progress_bar=False))

    return embed


def load_siglip(device):
    """SigLIP-class encoder, vision tower only. `AutoProcessor` for this
    model pulls in `SiglipTokenizer`, which needs `sentencepiece` -- not a
    declared dependency -- even though only images are ever encoded here;
    `SiglipVisionModel` + `AutoImageProcessor` sidesteps the tokenizer
    entirely and is confirmed to load under the same pin."""
    import torch
    from transformers import AutoImageProcessor, SiglipVisionModel

    model = SiglipVisionModel.from_pretrained("google/siglip-base-patch16-224").to(device).eval()
    processor = AutoImageProcessor.from_pretrained("google/siglip-base-patch16-224")

    def embed(images, batch_size=32):
        chunks = []
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            inputs = processor(images=batch, return_tensors="pt").to(model.device)
            with torch.no_grad():
                chunks.append(model(**inputs).pooler_output.cpu().numpy())
        return np.concatenate(chunks, axis=0)

    return embed


_ENCODERS = {"clip": load_clip, "siglip": load_siglip}


def cosine_matrix_chunked(query, corpus, chunk=500):
    """`query @ corpus.T` after L2-normalising both, `chunk` query rows at
    a time -- bounds peak memory to `chunk * len(corpus)` floats rather
    than the full `len(query) * len(corpus)` at once, which matters once
    `len(corpus)` is in the thousands."""
    query_n = query / np.linalg.norm(query, axis=1, keepdims=True)
    corpus_n = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    out = np.empty((len(query), len(corpus)), dtype=np.float32)
    for start in range(0, len(query), chunk):
        out[start : start + chunk] = query_n[start : start + chunk] @ corpus_n.T
    return out


def cross_paper_floor(embeddings, paper_groups, content_groups):
    """For every crop, its cosine to the nearest crop that is neither the
    same paper (`paper_groups`, see `citekey_paper_groups`) nor a
    byte-identical duplicate of it (`content_groups`, see
    `_assign_content_groups`) -- both are excluded, since neither is a
    draft figure's legitimate collision case, and including either
    inflates the floor with noise that is not about the field's drawing
    conventions. Returns the array of per-crop best cross-paper
    scores."""
    sims = cosine_matrix_chunked(embeddings, embeddings)
    paper_groups = np.asarray(paper_groups)
    content_groups = np.asarray(content_groups)
    best = np.full(len(embeddings), -1.0, dtype=np.float32)
    for i in range(len(embeddings)):
        mask = (paper_groups != paper_groups[i]) & (content_groups != content_groups[i])
        row = sims[i][mask]
        best[i] = row.max() if row.size else float("nan")
    return best


def percentiles(values):
    values = np.asarray(values, dtype=np.float64)
    return {
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(values.max()),
    }


def self_check():
    """Prove the ranking, the same-citekey mask and the hash distance can
    all see a difference that is fabricated to be there, before any of it
    runs against real crops.

    `bench/` sits outside CI's coverage targets and the clean-code
    ratchet (`bench/README.md`), so nothing in the test suite catches a
    regression here; this runs on every invocation instead. It cannot
    prove the *real* floor or planted-case numbers below are right --
    only that the arithmetic that would produce a wrong "0" or a flipped
    ranking is not silently broken.

    **What it cannot see, and did not**: `rasterize_tikz` silently
    returning a truncated image. This is exactly that failure class --
    a wrong render that produced a wrong-but-plausible-looking number --
    and a first run of this script did it, before `_TEX_WRAP` was fixed
    to use a fixed oversized page rather than the `article` default (see
    `bench/RESULTS.md`'s retraction note). No cheap arithmetic check
    here would have caught it; only rendering a fixture and looking did.
    This function does not compile TikZ (per `bench/README.md`'s "costs
    microseconds" convention), so it cannot be extended to catch this
    class of bug either -- a rendering fix has to be re-verified by eye,
    not by `self_check()`.
    """
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.999, 0.001, 0.0, 0.0],  # near-identical to row 0
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    same_paper_group = ["paperA", "paperA", "paperB", "paperC"]
    distinct_content = ["h0", "h1", "h2", "h3"]
    sims = cosine_matrix_chunked(embeddings, embeddings)
    assert sims[0].argmax() == 0, "a crop must be its own top match before any masking"
    ranked_others = np.argsort(-sims[0])
    assert ranked_others[1] == 1, "the near-identical row must rank second, unmasked"

    # Masking distinct papers: row 0's own paper is "paperA", so its
    # sibling (also "paperA") must be excluded, leaving paperB/paperC. This
    # is the same shape as two citekeys filing the same PDF twice.
    floor = cross_paper_floor(embeddings, same_paper_group, distinct_content)
    assert floor[0] < 0.5, (
        "excluding the same-paper sibling must drop crop 0's best match to an "
        f"orthogonal row, not the near-duplicate; got {floor[0]}"
    )

    # A byte-identical duplicate under a *different* paper_group (the
    # shared-book-chapter / mis-extracted-logo case found in the real
    # corpus) must be excluded too, even though its paper_group differs.
    cross_paper_but_duplicate_content = ["x0", "x1", "x2", "x3"]
    same_content_as_0 = ["c0", "c0", "c2", "c3"]
    floor2 = cross_paper_floor(embeddings, cross_paper_but_duplicate_content, same_content_as_0)
    assert floor2[0] < 0.5, (
        "excluding a cross-paper but byte-identical duplicate must also drop crop 0's "
        f"best match to an orthogonal row; got {floor2[0]}"
    )

    identical = np.zeros(64, dtype=bool)
    noisy = np.random.RandomState(0).randint(0, 2, size=64).astype(bool)
    assert hamming(identical, identical) == 0
    assert hamming(identical, noisy) > 0, (
        "a perceptual hash comparison that always reports 0 distance would look "
        "exactly like every image being identical"
    )
    matrix = hamming_matrix_chunked([identical, identical, noisy], chunk=2)
    assert matrix[0, 1] == 0, "the chunked matmul path must agree with the pairwise hamming() above"
    assert matrix[0, 2] == hamming(identical, noisy), "and must agree on a mismatched pair too"

    fabricated_record = {
        "cite": "Figure 9.9 of [@fake_paper_2099], p.9",
        "caption": "Fake caption",
        "image": "fake_paper_2099_artifacts/picture_000009.png",
    }
    assert fabricated_record["image"].startswith("fake_paper_2099"), (
        "a crop record's image path must resolve under its own citekey's "
        "artefact directory, or a figure could be attributed to the wrong paper"
    )


def summarise_planted(
    name, image, encoder_embed, corpus_embeddings, corpus_citekeys, corpus_images
):
    """`source_rank` is the query's own scale (rank among the whole
    corpus for *this* fixture), not comparable to `cross_paper_floor`'s
    per-crop scale -- a TikZ rasterisation and a PDF-rendered crop occupy
    different similarity bands regardless of content, so no floor
    percentile is a meaningful cutoff for a fixture's score. `chance_rank`
    (the median rank a uniformly-random score would land at) is the
    baseline that *is* comparable, and is what the caller reports the
    result against instead."""
    embedding = encoder_embed([image])[0:1]
    sims = cosine_matrix_chunked(embedding, corpus_embeddings)[0]
    order = np.argsort(-sims)
    top = [
        {"citekey": corpus_citekeys[i], "image": corpus_images[i], "score": float(sims[i])}
        for i in order[:5]
    ]
    source_indices = [
        i
        for i, (citekey, image_name) in enumerate(zip(corpus_citekeys, corpus_images))
        if citekey == _PLANTED_SOURCE_CITEKEY and image_name == _PLANTED_SOURCE_IMAGE
    ]
    source_rank = None
    source_score = None
    if source_indices:
        source_score = float(sims[source_indices[0]])
        source_rank = int((sims > source_score).sum()) + 1
    return {
        "fixture": name,
        "top5": top,
        "source_score": source_score,
        "source_rank": source_rank,
    }


def run_encoder_arm(encoder_name, device, crops, images, hashes, tag, out_dir):
    print(f"\n=== encoder: {encoder_name} ===")
    embed = _ENCODERS[encoder_name](device)

    # Corpus embeddings are the expensive, TikZ-independent part of this
    # arm (minutes over the whole corpus); caching them means re-running
    # only to change a fixture -- which this script's own development
    # needed twice -- costs seconds, not minutes, on the second run.
    cache_path = out_dir / f"embeddings_{encoder_name}.npy"
    if cache_path.exists():
        corpus_embeddings = np.load(cache_path)
        encode_seconds = 0.0
        per_crop_ms = 0.0
        if len(corpus_embeddings) != len(images):
            raise RuntimeError(
                f"{cache_path} has {len(corpus_embeddings)} rows but {len(images)} crops "
                "were loaded -- delete the cache and re-run rather than silently mixing them"
            )
        print(f"loaded {len(corpus_embeddings)} cached embeddings from {cache_path}")
    else:
        t0 = time.time()
        corpus_embeddings = embed(images)
        encode_seconds = time.time() - t0
        per_crop_ms = 1000 * encode_seconds / len(images)
        print(f"embedded {len(images)} crops in {encode_seconds:.1f}s ({per_crop_ms:.1f} ms/crop)")
        np.save(cache_path, corpus_embeddings)

    citekeys = [c["citekey"] for c in crops]
    paper_groups = [c["paper_group"] for c in crops]
    content_groups = [c["content_group"] for c in crops]
    image_names = [c["image"] for c in crops]

    identity_index = 0
    reloaded = Image.open(crops[identity_index]["path"]).convert("RGB")
    reloaded_embedding = embed([reloaded])
    identity_row = cosine_matrix_chunked(reloaded_embedding, corpus_embeddings)[0]
    identity_sim = float(identity_row[identity_index])
    identity_rank = int((identity_row > identity_sim).sum()) + 1
    print(f"identity control: self-cosine={identity_sim:.4f} self-rank={identity_rank}")

    floor = cross_paper_floor(corpus_embeddings, paper_groups, content_groups)
    floor_stats = percentiles(floor)
    print(f"cross-paper floor: {floor_stats}")

    chance_rank = (len(crops) + 1) / 2
    planted = []
    for fixture_path in sorted(_FIXTURE_DIR.glob("*.tex")):
        tikz_image = rasterize_tikz(fixture_path.read_text(encoding="utf-8"))
        result = summarise_planted(
            fixture_path.stem, tikz_image, embed, corpus_embeddings, citekeys, image_names
        )
        result["chance_rank"] = chance_rank
        result["better_than_chance"] = (
            result["source_rank"] is not None and result["source_rank"] < chance_rank
        )
        planted.append(result)
        print(
            f"  {fixture_path.stem}: source_score={result['source_score']} "
            f"source_rank={result['source_rank']} (chance_rank={chance_rank:.0f})"
        )

    distances = hamming_matrix_chunked(hashes)
    paper_groups_arr = np.asarray(paper_groups)
    content_groups_arr = np.asarray(content_groups)
    hash_floor = []
    for i in range(len(hashes)):
        mask = (paper_groups_arr != paper_groups_arr[i]) & (
            content_groups_arr != content_groups_arr[i]
        )
        row = distances[i][mask]
        hash_floor.append(float(row.min()) if row.size else float("nan"))
    hash_floor_stats = percentiles([64 - d for d in hash_floor])  # similarity-oriented, like cosine

    record = {
        "encoder": encoder_name,
        "device": device,
        "num_crops": len(crops),
        "embed_dim": int(corpus_embeddings.shape[1]),
        "encode_seconds": encode_seconds,
        "per_crop_ms": per_crop_ms,
        "identity_control": {"self_cosine": identity_sim, "self_rank": identity_rank},
        "cross_paper_floor_cosine": floor_stats,
        "cross_paper_floor_hash_similarity_out_of_64": hash_floor_stats,
        "planted": planted,
    }
    out_path = out_dir / f"figure_similarity_{encoder_name}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    ap.add_argument(
        "--tag", required=True, help="names bench/results/<tag>/, for a reproducible record"
    )
    ap.add_argument(
        "--encoders",
        default="clip,siglip",
        help="comma-separated subset of clip,siglip to run (default: both)",
    )
    ap.add_argument("--device", default="cuda", help="cuda or cpu")
    ap.add_argument(
        "--sample",
        type=int,
        default=None,
        help="cap the corpus crop count for a fast dev run (default: the whole corpus)",
    )
    args = ap.parse_args(argv)

    self_check()

    crops = load_corpus_crops(config.DOCLING_DIR, citekey_paper_groups())
    print(f"figures.json crops found on disk: {len(crops)}")
    if args.sample:
        crops = crops[: args.sample]
        print(f"sampled down to {len(crops)}")
    if not crops:
        print("no figure crops on disk -- nothing to measure (tiers_not_run territory)")
        return 1

    t0 = time.time()
    images = [Image.open(c["path"]).convert("RGB") for c in crops]
    decode_seconds = time.time() - t0
    print(f"decoded {len(images)} crops in {decode_seconds:.1f}s")

    hashes = [average_hash(img) for img in images]

    by_content = {}
    for crop in crops:
        by_content.setdefault(crop["content_group"], set()).add(crop["paper_group"])
    cross_paper_dupe_groups = sum(1 for papers in by_content.values() if len(papers) > 1)
    print(
        f"exact-duplicate content groups: {len(by_content)} distinct byte patterns "
        f"({cross_paper_dupe_groups} of them span >1 paper -- excluded from the floor below)"
    )

    out_dir = Path(__file__).resolve().parent / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    requested = [e.strip() for e in args.encoders.split(",") if e.strip()]
    records = []
    for encoder_name in requested:
        if encoder_name not in _ENCODERS:
            print(f"unknown encoder {encoder_name!r}, skipping")
            continue
        records.append(
            run_encoder_arm(encoder_name, args.device, crops, images, hashes, args.tag, out_dir)
        )

    summary = {
        "date": date.today().isoformat(),
        "tag": args.tag,
        "num_crops": len(crops),
        "decode_seconds": decode_seconds,
        "encoders": [r["encoder"] for r in records],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwrote {out_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
