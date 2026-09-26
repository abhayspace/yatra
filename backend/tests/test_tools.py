"""Unit tests for the travel agent's tools — no network calls."""

import ast

from app.agent.tools import _evaluate, calculate


def _eval_expr(expr: str):
    return _evaluate(ast.parse(expr, mode="eval").body)


# ── Calculator: happy path ──────────────────────────────────────────────

def test_calculate_basic_arithmetic():
    assert calculate.invoke({"expression": "25 * 4"}) == "100"
    assert calculate.invoke({"expression": "10 + 5"}) == "15"
    assert calculate.invoke({"expression": "10 % 3"}) == "1"
    assert calculate.invoke({"expression": "2 ** 10"}) == "1024"


def test_calculate_negative_and_float():
    assert calculate.invoke({"expression": "-5 + 3"}) == "-2"
    assert float(calculate.invoke({"expression": "150 / 5 + 10"})) == 40.0


# ── Calculator: safety ──────────────────────────────────────────────────

def test_calculate_rejects_injection():
    for payload in [
        "__import__('os').system('id')",
        "open('/etc/passwd').read()",
        "().__class__.__bases__",
        "exec('print(1)')",
        "1; import os",
    ]:
        result = calculate.invoke({"expression": payload})
        assert "error" in result.lower(), payload


def test_calculate_rejects_giant_exponent():
    result = calculate.invoke({"expression": "2 ** 100000"})
    assert "exponent" in result.lower()


def test_calculate_division_by_zero():
    result = calculate.invoke({"expression": "10 / 0"})
    assert "error" in result.lower()


def test_calculate_empty_and_garbage():
    assert "error" in calculate.invoke({"expression": ""}).lower()
    assert "error" in calculate.invoke({"expression": "abc"}).lower()


# ── AST evaluator internals ─────────────────────────────────────────────

def test_evaluate_rejects_non_constant_atoms():
    import pytest

    with pytest.raises(ValueError):
        _eval_expr("x + 1")  # names not allowed
    with pytest.raises(ValueError):
        _eval_expr("f(1)")   # calls not allowed
    with pytest.raises(ValueError):
        _eval_expr("'string'")


def test_evaluate_rejects_disallowed_ops():
    import pytest

    with pytest.raises(ValueError):
        _eval_expr("1 << 2")   # bitshift not in allowlist
    with pytest.raises(ValueError):
        _eval_expr("~5")       # invert not in allowlist
