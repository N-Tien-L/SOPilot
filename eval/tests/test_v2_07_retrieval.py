"""V2-07 pre-run changes: final BM25 tokenizer, hybrid dense gate, cross-lingual BM25 factor, span metrics."""
import numpy as np
import pytest

from sopilot_eval.corpus import Chunk
from sopilot_eval.metrics import span_metrics
from sopilot_eval.retrievers import (
    BM25,
    fold,
    gate_score,
    lexical_len,
    retrieve_candidates,
    rrf,
    tokenize,
)


def test_fold_strips_vietnamese_diacritics_and_d_bar():
    assert fold("đường_hàng") == "duong_hang"
    assert fold("laptop") == "laptop"


def test_document_terms_add_folded_variant_only_when_changed():
    # Arrange / Act
    terms = tokenize("Mua hàng laptop")
    # Assert
    assert "~hang" in terms and "~mua_hang" in terms
    assert "~laptop" not in terms and "~mua" not in terms
    assert lexical_len("Mua hàng laptop") == 5  # 3 unigrams + 2 bigrams, no ~ terms


def test_query_without_diacritics_adds_tilde_terms_and_matches_accented_doc():
    # Arrange
    bm25 = BM25([tokenize("quy trình mua hàng"), tokenize("other text")],
                lengths=[lexical_len("quy trình mua hàng"), lexical_len("other text")])
    # Act
    plain = tokenize("quy trinh mua hang", role="query")
    accented = tokenize("quy trình", role="query")
    # Assert
    assert "~quy_trinh" in plain
    assert all(not t.startswith("~") for t in accented)
    assert bm25.scores(plain)[0] > 0 and bm25.scores(plain)[1] == 0


def test_bm25_has_no_gate_and_rerank_gates_on_rerank_score():
    assert gate_score("bm25", {"dense_score": None}) is None
    assert gate_score("hybrid_rerank", {"rerank_score": 0.7, "dense_score": 0.1}) == 0.7
    with pytest.raises(ValueError):
        gate_score("hybrid", {"dense_score": None})


class _Index:
    def __init__(self, dense, sparse, langs):
        self._d, self._s = np.array(dense), np.array(sparse)
        self.chunks = [Chunk("d", 1, "t", lang=lang) for lang in langs]

    def dense(self, _):
        return self._d

    def sparse(self, _):
        return self._s


def test_hybrid_lexical_only_candidate_keeps_its_cosine_gate():
    # Arrange: chunk 1 is ranked by BM25 only (weights put all mass on BM25)
    index = _Index([0.8, 0.1], [0.0, 5.0], ["vi", "vi"])
    # Act
    cands = retrieve_candidates(index, "q", {"retriever": "hybrid", "weights": [0, 1]}, None)
    # Assert
    assert cands[0]["idx"] == 1
    assert cands[0]["gate"] == pytest.approx(0.1) and cands[0]["bm25_score"] == pytest.approx(5.0)


def test_cross_lingual_factor_scales_only_other_language_bm25_items():
    # Arrange: BM25 prefers the English chunk 1, dense prefers Vietnamese chunk 0
    index = _Index([0.9, 0.2, 0.1], [0.0, 9.0, 1.0], ["vi", "en", "vi"])
    base = {"retriever": "hybrid", "weights": [1.0, 1.0]}
    # Act
    zero = retrieve_candidates(index, "q", {**base, "cross_lingual_bm25_factor": 0.0}, None, query_lang="vi")
    unknown = retrieve_candidates(index, "q", {**base, "cross_lingual_bm25_factor": 0.0}, None, query_lang=None)
    # Assert
    fused_en = next(c for c in zero if c["idx"] == 1)["fusion_score"]
    assert fused_en == pytest.approx(1 / 62)  # only its dense contribution (dense rank 2)
    assert next(c for c in unknown if c["idx"] == 1)["fusion_score"] > fused_en


def test_rrf_item_weights_default_to_one():
    assert rrf([[0, 1]], [1.0], item_weights=[{}]) == rrf([[0, 1]], [1.0])


def _chunk(doc_id, start, end):
    return Chunk(doc_id + ".md", 1, "x", char_start=start, char_end=end, doc_id=doc_id)


def test_span_metrics_require_every_span_of_one_alternative():
    # Arrange
    spans = {
        "a": {"doc_id": "d", "start_char": 10, "end_char": 20},
        "b": {"doc_id": "d", "start_char": 100, "end_char": 110},
        "c": {"doc_id": "e", "start_char": 0, "end_char": 10},
    }
    ranked = [_chunk("d", 0, 50), _chunk("x", 0, 9), _chunk("d", 95, 200)]
    # Act
    m = span_metrics(ranked, [["a", "b"], ["c"]], spans, ks=(1, 3))
    # Assert
    assert m["span_recall@1"] == 0.5 and m["full@1"] == 0.0 and m["any@1"] == 1.0
    assert m["full@3"] == 1.0 and m["mrr_span"] == 1.0


def test_span_split_across_two_chunks_counts_their_union():
    spans = {"a": {"doc_id": "d", "start_char": 10, "end_char": 30}}
    m = span_metrics([_chunk("d", 0, 15), _chunk("d", 15, 40)], [["a"]], spans, ks=(1, 2))
    assert m["any@1"] == 0.0 and m["full@2"] == 1.0


def test_threshold_is_picked_on_dev_by_min_total_error_lowest_on_tie():
    from sopilot_eval.analyze_v2_07 import pick_threshold, sweep

    rows = [{"answerable": True, "gate_score": s} for s in (0.6, 0.7, 0.8)]
    rows += [{"answerable": False, "gate_score": s} for s in (0.3, 0.65)]
    picked = pick_threshold(rows)
    # 0.675 refuses one answerable (1/3) and no negative: total 0.33 beats 0.45 (0 + 0.5)
    assert picked["threshold"] == pytest.approx(0.675)
    assert sweep(rows, picked["threshold"]) == (pytest.approx(1 / 3), 0.0)
