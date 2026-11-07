from sopilot_eval.crossref import (
    code_key,
    find_refs,
    is_self_attachment,
    is_self_mention,
    own_number,
    resolve,
    strip_furniture,
)


def test_vietnamese_references():
    text = (
        "Thực hiện theo mục 5.3 và Điều 12, khoản 2. Lập biểu mẫu BM-01-02 theo QT-05 "
        "và Nghị định số 30/2020/NĐ-CP, TCVN ISO 9001:2015. Áp dụng luật hiện hành; "
        "Luật Thanh tra năm 2010 quy định."
    )
    refs = find_refs(text)
    assert refs["within_document"] == ["mục 5.3", "Điều 12", "khoản 2"]
    assert refs["between_documents"] == [
        "BM-01-02",
        "QT-05",
        "Nghị định số 30/2020/NĐ-CP",
        "TCVN ISO 9001:2015",
        "Luật Thanh tra",
    ]


def test_english_references():
    text = (
        "See Section 3.2.2 and Step 5.1; complete Attachment 1. Follow SOP 21918, "
        "LSASDPROC-206, ORA-LAB.5.8 and 21CFR211.101(b)."
    )
    refs = find_refs(text)
    assert refs["within_document"] == ["Section 3.2.2", "Step 5.1", "Attachment 1"]
    assert refs["between_documents"] == ["SOP 21918", "LSASDPROC-206", "ORA-LAB.5.8", "21CFR211.101(b)"]


def test_dates_and_lowercase_words_are_not_references():
    refs = find_refs("Ngày ban hành 05/11/2020, sop lỏng, hd viên, luật chơi.")
    assert refs == {"within_document": [], "between_documents": []}


def test_code_key_normalizes_separators():
    assert code_key("QT.05") == code_key("QT-05") == code_key("qt 05")
    assert code_key("Nghị định số 30/2020/NĐ-CP") == "30/2020/nđ-cp"


def test_forms_of_the_document_itself_are_within():
    own = own_number("QT-01")
    assert is_self_attachment("BM-01-02", own)
    assert is_self_attachment("BM.QT.01.03", own)
    assert not is_self_attachment("QT-01", own)
    assert not is_self_attachment("BM-02-01", own)
    assert is_self_attachment("QT.03.01", own_number("QT.03"))


def test_own_code_is_not_a_reference():
    assert is_self_mention("LSASDPROC-300", code_key("LSASDPROC-300-R5"))
    assert is_self_mention("1308/QĐ-TTg", code_key("1308/QĐ-TTg"))
    assert not is_self_mention("LSASDPROC-301", code_key("LSASDPROC-300-R5"))


def test_internal_codes_resolve_only_within_the_same_issuer():
    aliases = {code_key("QT-02"): ["tb-qt02", "nb-qt02"], "30/2020/nđ-cp": ["nd30"]}
    hosts = {"nb-qt02": "a.gov.vn", "nb-qt04": "a.gov.vn", "tb-qt02": "b.gov.vn", "nd30": "c.gov.vn"}
    assert resolve("QT-02", aliases, hosts, "nb-qt04") == "nb-qt02"
    assert resolve("Nghị định 30/2020/NĐ-CP", aliases, hosts, "nb-qt04") == "nd30"
    assert resolve("QT-07", aliases, hosts, "nb-qt04") is None


def test_furniture_lines_are_removed_before_counting():
    text = "SOP Number: 21301\nBody cites SOP 21918.\nPage 2 of 17"
    body = strip_furniture(text, ["SOP Number: 21301", "Page 2 of 17"])
    assert find_refs(body)["between_documents"] == ["SOP 21918"]
