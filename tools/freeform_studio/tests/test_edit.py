from freeform_studio.edit import normalize_edit, validate_edit


def seg(i, a, b, text="hello there.", status="pending", **kw):
    d = {"id": f"s{i:03d}", "start": a, "end": b, "text": text, "words": [], "status": status,
         "tags": [], "note": "", "flags": [], "auto": None}
    d.update(kw)
    return d


def doc(*segs):
    return {"schema": 1, "rev": 1, "segments": list(segs)}


def test_valid_document_passes():
    assert validate_edit(doc(seg(1, 0.0, 2.0), seg(2, 2.5, 4.0, status="approved")), 5.0) == []


def test_rejects_overlap_out_of_order_and_out_of_range():
    errs = validate_edit(doc(seg(1, 0.0, 2.0), seg(2, 1.5, 3.0)), 5.0)
    assert any("overlaps" in e for e in errs)
    errs = validate_edit(doc(seg(1, 0.0, 6.0)), 5.0)
    assert any("outside the recording" in e for e in errs)
    errs = validate_edit(doc(seg(1, 1.0, 1.01)), 5.0)
    assert any("shorter than" in e for e in errs)


def test_rejects_duplicate_and_malformed_ids():
    assert any("duplicate" in e for e in validate_edit(doc(seg(1, 0, 1), seg(1, 2, 3)), 5.0))
    assert any("bad id" in e for e in validate_edit(doc(seg(1, 0, 1, id="x1")), 5.0))


def test_text_rules_protect_the_training_csv():
    assert any("'|'" in e for e in validate_edit(doc(seg(1, 0, 1, text="a | b")), 5.0))
    assert any("line breaks" in e for e in validate_edit(doc(seg(1, 0, 1, text="a\nb")), 5.0))
    assert any("longer than" in e for e in validate_edit(doc(seg(1, 0, 1, text="x" * 2001)), 5.0))


def test_cannot_approve_empty_text_and_status_enum():
    assert any("no text" in e for e in validate_edit(doc(seg(1, 0, 1, text="  ", status="approved")), 5.0))
    assert any("status" in e for e in validate_edit(doc(seg(1, 0, 1, status="maybe")), 5.0))


def test_tags_and_note_limits():
    assert any("tags" in e for e in validate_edit(doc(seg(1, 0, 1, tags=["Bad Tag"])), 5.0))
    assert any("tags" in e for e in validate_edit(doc(seg(1, 0, 1, tags=["a"] * 9)), 5.0))
    assert any("note" in e for e in validate_edit(doc(seg(1, 0, 1, note="n" * 501)), 5.0))
    assert validate_edit(doc(seg(1, 0, 1, tags=["laugh", "noisy"])), 5.0) == []


def test_non_numbers_are_rejected_not_crashed_on():
    assert any("numbers" in e for e in validate_edit(doc(seg(1, "a", 1)), 5.0))
    assert any("numbers" in e for e in validate_edit(doc(seg(1, float("nan"), 1)), 5.0))
    assert any("numbers" in e for e in validate_edit(doc(seg(1, True, 1)), 5.0))
    assert validate_edit({"segments": "nope"}, 5.0) == ["segments must be a list"]


def test_normalize_drops_unknown_keys():
    raw = {"rev": 3, "evil": "x", "segments": [{**seg(1, 0, 1), "script": "<b>"}]}
    out = normalize_edit(raw)
    assert "evil" not in out and "script" not in out["segments"][0] and out["rev"] == 3
