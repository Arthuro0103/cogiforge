"""demo/ is the fixture: one planted failure per file, and the controls pass clean."""
import counts


def test_exact_count_per_check():
    found = counts.count()
    for check, file in counts.EXPECTED.items():
        assert sorted(found[check]) == [file], check


def test_no_control_fails():
    found = counts.count()
    failed = {a for c in counts.EXPECTED for a in found[c]}
    assert failed == set(counts.EXPECTED.values())


def test_total_notes_and_inbox_exemption():
    found = counts.count()
    assert found["_total"] == counts.TOTAL_NOTES
    assert found["_exempt"] == counts.RING_EXEMPT


def test_no_unexpected_check():
    found = counts.count()
    assert set(found) - {"_total", "_exempt"} == set(counts.EXPECTED)
