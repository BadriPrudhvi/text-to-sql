from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from text_to_sql.models.domain import ColumnInfo, TableInfo
from text_to_sql.schema.selector import TableSelector, _tokenize


def _make_tables() -> list[TableInfo]:
    return [
        TableInfo(
            table_name="users",
            description="Application users",
            columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
                ColumnInfo(name="email", data_type="TEXT"),
            ],
        ),
        TableInfo(
            table_name="orders",
            description="Customer purchase orders",
            columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
                ColumnInfo(name="user_id", data_type="INTEGER"),
                ColumnInfo(name="total_amount", data_type="DECIMAL"),
            ],
        ),
        TableInfo(
            table_name="products",
            columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
                ColumnInfo(name="name", data_type="TEXT"),
                ColumnInfo(name="price", data_type="DECIMAL"),
            ],
        ),
        TableInfo(
            table_name="audit_logs",
            columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
                ColumnInfo(name="action", data_type="TEXT"),
            ],
        ),
    ]


# --- Tokenizer tests ---


def test_tokenize_underscores() -> None:
    assert _tokenize("order_items") == {"order", "items"}


def test_tokenize_camel_case() -> None:
    assert _tokenize("orderItems") == {"order", "items"}


def test_tokenize_mixed() -> None:
    tokens = _tokenize("user_orderItems_v2")
    assert "user" in tokens
    assert "order" in tokens
    assert "items" in tokens


# --- Keyword selector tests ---


def test_keyword_matches_table_name() -> None:
    selector = TableSelector()
    tables = _make_tables()
    result = selector.select_by_keywords("Show me all users", tables)
    assert result[0].table_name == "users"


def test_keyword_matches_column_name() -> None:
    selector = TableSelector()
    tables = _make_tables()
    result = selector.select_by_keywords("What is the total amount?", tables)
    assert any(t.table_name == "orders" for t in result)


def test_keyword_matches_description() -> None:
    selector = TableSelector()
    tables = _make_tables()
    result = selector.select_by_keywords("purchase history", tables)
    assert any(t.table_name == "orders" for t in result)


def test_keyword_no_match_fallback() -> None:
    selector = TableSelector()
    tables = _make_tables()
    result = selector.select_by_keywords("xyzzy foobar", tables)
    # Falls back to all tables
    assert len(result) == len(tables)


def test_keyword_respects_max() -> None:
    selector = TableSelector()
    tables = _make_tables()
    result = selector.select_by_keywords("Show me all users and orders", tables, max_tables=1)
    assert len(result) == 1


# --- LLM selector tests ---


@pytest.mark.asyncio
async def test_llm_parses_json_response() -> None:
    selector = TableSelector()
    tables = _make_tables()

    mock_model = AsyncMock()
    mock_model.ainvoke = AsyncMock(
        return_value=AIMessage(content='["users", "orders"]')
    )

    result = await selector.select_by_llm("Show user orders", tables, mock_model)
    names = [t.table_name for t in result]
    assert "users" in names
    assert "orders" in names


@pytest.mark.asyncio
async def test_llm_falls_back_on_bad_json() -> None:
    selector = TableSelector()
    tables = _make_tables()

    mock_model = AsyncMock()
    mock_model.ainvoke = AsyncMock(
        return_value=AIMessage(content="I think you need the users table")
    )

    result = await selector.select_by_llm("Show users", tables, mock_model)
    # Should fall back to keyword matching, which will find "users"
    assert any(t.table_name == "users" for t in result)
