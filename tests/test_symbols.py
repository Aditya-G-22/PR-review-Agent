"""Unit tests for symbols_in_diff — the regex that pulls function names out of a diff."""

from symbols import symbols_in_diff


def test_extracts_a_called_function():
    # Arrange: a diff line that calls a function
    diff = "--- a/x.py\n+++ b/x.py\n+    user = get_user_by_id(req)\n"
    # Act
    names = symbols_in_diff(diff)
    # Assert
    assert "get_user_by_id" in names


def test_ignores_words_that_are_not_calls():
    diff = "+    total = compute(price) + tax_rate\n"
    names = symbols_in_diff(diff)
    assert "compute" in names        # it's followed by "(" → a call
    assert "tax_rate" not in names   # not a call → must be ignored
    assert "total" not in names


def test_empty_diff_returns_empty_set():
    assert symbols_in_diff("") == set()
