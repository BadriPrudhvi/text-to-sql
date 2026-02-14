from __future__ import annotations

from text_to_sql.llm.sql_generator import SQLGenerator


def test_strip_code_fences_sql() -> None:
    raw = "```sql\nSELECT count(*) FROM users\n```"
    assert SQLGenerator._strip_code_fences(raw) == "SELECT count(*) FROM users"


def test_strip_code_fences_no_language() -> None:
    raw = "```\nSELECT 1\n```"
    assert SQLGenerator._strip_code_fences(raw) == "SELECT 1"


def test_strip_code_fences_plain() -> None:
    raw = "SELECT count(*) FROM users"
    assert SQLGenerator._strip_code_fences(raw) == "SELECT count(*) FROM users"


def test_strip_code_fences_with_whitespace() -> None:
    raw = "  ```sql\n  SELECT 1  \n```  "
    result = SQLGenerator._strip_code_fences(raw)
    assert "SELECT 1" in result
