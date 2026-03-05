from __future__ import annotations

import pytest

from text_to_sql.pipeline.validators import ResultValidator


@pytest.fixture
def validator() -> ResultValidator:
    return ResultValidator()


def test_no_warnings_for_good_result(validator: ResultValidator) -> None:
    result = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    warnings = validator.validate("SELECT * FROM users", result, "Show all users")
    assert warnings == []


def test_no_warnings_for_none_result(validator: ResultValidator) -> None:
    warnings = validator.validate("SELECT 1", None, "test")
    assert warnings == []


def test_empty_aggregate_warning(validator: ResultValidator) -> None:
    warnings = validator.validate(
        "SELECT COUNT(*) FROM users WHERE age > 100",
        [],
        "How many users over 100?",
    )
    assert len(warnings) == 1
    assert "Aggregate" in warnings[0]


def test_no_empty_aggregate_for_non_aggregate(validator: ResultValidator) -> None:
    warnings = validator.validate(
        "SELECT * FROM users WHERE age > 100",
        [],
        "Show users over 100",
    )
    assert not any("Aggregate" in w for w in warnings)


def test_suspicious_negative_in_count(validator: ResultValidator) -> None:
    result = [{"count": -5}]
    warnings = validator.validate("SELECT count FROM stats", result, "counts")
    assert len(warnings) == 1
    assert "negative" in warnings[0].lower()


def test_suspicious_negative_in_amount(validator: ResultValidator) -> None:
    result = [{"amount": -100.5}]
    warnings = validator.validate("SELECT amount FROM orders", result, "totals")
    assert any("negative" in w.lower() for w in warnings)


def test_no_negative_warning_for_non_amount_columns(validator: ResultValidator) -> None:
    result = [{"balance": -500}]
    warnings = validator.validate("SELECT balance FROM accounts", result, "balances")
    assert not any("negative" in w.lower() for w in warnings)


def test_no_negative_warning_for_positive_values(validator: ResultValidator) -> None:
    result = [{"count": 5}, {"count": 10}]
    warnings = validator.validate("SELECT count FROM stats", result, "counts")
    assert not any("negative" in w.lower() for w in warnings)


def test_limit_mismatch_warning(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(20)]
    warnings = validator.validate(
        "SELECT * FROM users LIMIT 20",
        result,
        "Show top 5 users",
    )
    assert len(warnings) == 1
    assert "top 5" in warnings[0]


def test_no_limit_mismatch_when_no_top_requested(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(10)]
    warnings = validator.validate(
        "SELECT * FROM users LIMIT 10",
        result,
        "Show all users",
    )
    assert not any("top" in w.lower() for w in warnings)


def test_no_limit_mismatch_when_matching(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(10)]
    warnings = validator.validate(
        "SELECT * FROM users LIMIT 10",
        result,
        "Show top 10 users",
    )
    assert not any("top" in w.lower() for w in warnings)


def test_cartesian_product_warning_with_join(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(15000)]
    sql = "SELECT a.id FROM orders a JOIN users b ON a.user_id = b.id LIMIT 10"
    warnings = validator.validate(sql, result, "Show orders with users")
    assert any("cartesian" in w.lower() for w in warnings)


def test_no_cartesian_warning_for_small_result(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(50)]
    sql = "SELECT a.id FROM orders a JOIN users b ON a.user_id = b.id"
    warnings = validator.validate(sql, result, "Show orders with users")
    assert not any("cartesian" in w.lower() for w in warnings)


def test_no_cartesian_warning_without_join(validator: ResultValidator) -> None:
    result = [{"id": i} for i in range(15000)]
    sql = "SELECT id FROM orders"
    warnings = validator.validate(sql, result, "Show all orders")
    assert not any("cartesian" in w.lower() for w in warnings)


def test_high_null_ratio_warning(validator: ResultValidator) -> None:
    result = [{"name": None} for _ in range(9)] + [{"name": "Alice"}]
    warnings = validator.validate("SELECT name FROM users", result, "Show names")
    assert any("null" in w.lower() for w in warnings)


def test_no_null_warning_for_low_ratio(validator: ResultValidator) -> None:
    result = [{"name": f"user_{i}"} for i in range(8)] + [{"name": None}, {"name": None}]
    warnings = validator.validate("SELECT name FROM users", result, "Show names")
    assert not any("null" in w.lower() for w in warnings)


def test_no_null_warning_for_small_result(validator: ResultValidator) -> None:
    result = [{"name": None}]
    warnings = validator.validate("SELECT name FROM users", result, "Show names")
    assert not any("null" in w.lower() for w in warnings)


def test_duplicate_row_warning(validator: ResultValidator) -> None:
    result = [{"id": 1, "name": "Alice"}] * 8 + [{"id": 2, "name": "Bob"}] * 2
    warnings = validator.validate("SELECT * FROM users", result, "Show users")
    assert any("duplicate" in w.lower() for w in warnings)


def test_no_duplicate_warning_for_unique_rows(validator: ResultValidator) -> None:
    result = [{"id": i, "name": f"user_{i}"} for i in range(10)]
    warnings = validator.validate("SELECT * FROM users", result, "Show users")
    assert not any("duplicate" in w.lower() for w in warnings)


def test_no_duplicate_warning_for_small_result(validator: ResultValidator) -> None:
    result = [{"id": 1}] * 3
    warnings = validator.validate("SELECT * FROM t", result, "test")
    assert not any("duplicate" in w.lower() for w in warnings)
