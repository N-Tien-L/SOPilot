from sopilot_eval.pilot_chunks import (
    markdown_sha256,
    no_letters,
    step_chunks,
    uncovered_body,
    under_min,
)


def _chunk(kind="TEXT", tokens=100, content="abc", start=0, end=10):
    return {"kind": kind, "token_count": tokens, "content": content,
            "char_start": start, "char_end": end}


def test_under_min_ignores_procedure_steps():
    chunks = [_chunk(tokens=10), _chunk(kind="PROCEDURE_STEP", tokens=5), _chunk(tokens=64)]
    assert under_min(chunks, 64) == 1
    assert step_chunks(chunks) == 1


def test_a_chunk_of_underscores_has_no_letters():
    assert no_letters([_chunk(content="____ 12 ..."), _chunk(content="a")]) == 1


def test_vietnamese_letters_count_as_letters():
    assert no_letters([_chunk(content="ệ")]) == 0


def test_a_body_element_inside_a_chunk_is_covered():
    count, examples = uncovered_body([(2, 5, True)], [_chunk(start=0, end=10)], "x" * 10)
    assert (count, examples) == (0, [])


def test_a_body_element_outside_every_chunk_is_uncovered():
    md = "aaaa\n\n   lost   text  here"
    count, examples = uncovered_body([(6, len(md), True)], [_chunk(start=0, end=4)], md)
    assert count == 1
    assert examples == ["lost text here"]


def test_a_heading_outside_chunks_is_not_counted():
    count, _ = uncovered_body([(6, 12, False)], [_chunk(start=0, end=4)], "x" * 12)
    assert count == 0


def test_markdown_sha256_is_stable():
    assert markdown_sha256("a") == \
        "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
