"""Vietnamese SOP system check (V2-28): dataset schema, runner behaviour with fake pipelines."""

from __future__ import annotations

from pathlib import Path

from sopilot_eval import system_check as sc

EVAL_ROOT = Path(__file__).resolve().parents[1]
CONFIG = EVAL_ROOT / "configs" / "vi-sop-check.yaml"
QUESTIONS = EVAL_ROOT / "datasets" / "vi-sop-check" / "questions.jsonl"


def _dataset() -> sc.Dataset:
    return sc.load_dataset(QUESTIONS)


def test_dataset_schema_is_valid_and_sizes_meet_minimum():
    dataset = _dataset()
    assert dataset.errors == []
    rows = sc.build_rows(dataset)
    assert sc.validate_group_sizes(rows, min_rows=4) == []
    assert 30 <= len(rows) <= 40  # ticket: 30-40 Vietnamese questions
    assert {r["group"] for r in rows} == set(sc.GROUP_ORDER)


def test_group_c_questions_contain_their_document_code():
    rows = sc.build_rows(_dataset())
    group_c = [r for r in rows if r["group"] == sc.GROUPS["c"]]
    assert len(group_c) >= 4
    assert all(r["doc_code"] in r["question"] for r in group_c)


def test_long_question_over_1000_chars_exists_and_expects_input_invalid():
    rows = sc.build_rows(_dataset())
    long_rows = [r for r in rows if len(r["question"]) > sc.MAX_QUESTION_CHARS]
    assert long_rows, "group h needs a question over 1000 characters"
    for row in long_rows:
        assert row["group"] == sc.GROUPS["h"]
        assert row["expected_refusal"] == "INPUT_INVALID"


def test_dev_and_test_do_not_overlap():
    dataset = _dataset()
    rows = sc.build_rows(dataset)
    dev_ids = {r["id"] for r in rows if r["split"] == "dev"}
    test_ids = {r["id"] for r in rows if r["split"] == "test"}
    assert dev_ids and test_ids
    assert dev_ids.isdisjoint(test_ids)
    assert sc.validate_split_separation(rows) == []


def test_group_e_is_generated_deterministically_and_unaccented():
    rows = _dataset().hand_rows
    first = sc.generate_group_e(rows)
    second = sc.generate_group_e(rows)
    assert first == second
    assert len(first) == sc.UNACCENT_COUNT
    base_by_id = {r["id"]: r for r in rows}
    for variant in first:
        assert variant["group"] == sc.GROUP_E
        assert variant["question"].isascii()
        assert variant["question"] == sc.unaccent(base_by_id[variant["base_id"]]["question"])
        assert variant["split"] == base_by_id[variant["base_id"]]["split"]
        assert variant["evidence_sets"] == base_by_id[variant["base_id"]]["evidence_sets"]
    assert {v["split"] for v in first} == {"dev", "test"}


def test_unaccent_removes_diacritics_and_punctuation():
    assert sc.unaccent("Đơn vị nào phê duyệt, ở bước 3?") == "don vi nao phe duyet o buoc 3"


def test_validator_rejects_answerable_row_without_evidence():
    dataset = _dataset()
    row = dict(dataset.hand_rows[0], evidence_sets=[])
    errors = sc.validate_rows([row], dataset.spans)
    assert any("need evidence_sets" in e for e in errors)


def test_runner_with_wrong_pipeline_fails_acceptance(tmp_path):
    async def wrong(question: str) -> sc.Answer:
        return sc.Answer(outcome="ANSWERED", text="Không có thông tin trong tài liệu.")

    report = sc.run_system_check(CONFIG, asker=wrong, output=tmp_path / "wrong.json")
    assert report["overall"]["pass_rate"] < 1
    assert report["passed_acceptance"] is False
    assert (tmp_path / "wrong.json").is_file()


def test_runner_with_oracle_pipeline_passes_acceptance(tmp_path):
    dataset = _dataset()
    rows = sc.build_rows(dataset)
    by_question = {r["question"]: r for r in rows}

    async def oracle(question: str) -> sc.Answer:
        row = by_question[question]
        if row["group"] == sc.GROUPS["h"]:
            return sc.Answer(outcome="TEMPLATE", refusal_reason=row["expected_refusal"], text="Từ chối.")
        if row["group"] == sc.GROUPS["i"]:
            return sc.Answer(outcome="REFUSED_NO_EVIDENCE", text="Không có đáp án.")
        citations = tuple(
            sc.Citation(doc_id=dataset.spans[s]["doc_id"], start=dataset.spans[s]["start_char"],
                        end=dataset.spans[s]["end_char"])
            for group_set in row["evidence_sets"] for s in group_set)
        return sc.Answer(outcome="ANSWERED", text=" ".join(row["expected_terms"]), citations=citations)

    report = sc.run_system_check(CONFIG, asker=oracle, output=tmp_path / "oracle.json")
    assert report["overall"]["pass_rate"] == 1.0
    assert report["passed_acceptance"] is True


def test_runner_records_exception_as_failed_row_not_crash(tmp_path):
    async def broken(question: str) -> sc.Answer:
        raise RuntimeError("secret detail must not be kept")

    report = sc.run_system_check(CONFIG, asker=broken, output=tmp_path / "broken.json")
    assert report["overall"]["passed"] == 0
    assert all(r["error"] == "RuntimeError" for r in report["rows"])
    assert "secret detail" not in (tmp_path / "broken.json").read_text(encoding="utf-8")


def test_dry_run_needs_no_services_and_no_asker():
    report = sc.run_system_check(CONFIG, dry_run=True)
    assert report["mode"] == "dry-run"
    assert report["passed_acceptance"] is None


def test_config_paths_resolve_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = sc.run_system_check(CONFIG, dry_run=True)
    assert report["dataset"]["questions_file_rows"] == 33
    monkeypatch.chdir(EVAL_ROOT)
    report = sc.run_system_check(Path("configs/vi-sop-check.yaml"), dry_run=True)
    assert report["dataset"]["questions_file_rows"] == 33


def test_run_mode_without_principal_is_a_config_error():
    try:
        sc.run_system_check(CONFIG)
    except sc.ConfigError as exc:
        assert "principal" in str(exc)
    else:  # pragma: no cover - the placeholder config must not run against a stack
        raise AssertionError("run mode without principal must fail")
