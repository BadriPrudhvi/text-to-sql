from __future__ import annotations

from text_to_sql.models.domain import ApprovalStatus, ColumnInfo, QueryRecord, TableInfo
from text_to_sql.models.requests import ApprovalRequest, QueryRequest


def test_query_record_defaults() -> None:
    record = QueryRecord(natural_language="test", database_type="sqlite")
    assert record.approval_status == ApprovalStatus.PENDING
    assert record.generated_sql == ""
    assert record.result is None
    assert record.error is None
    assert record.id  # UUID is generated


def test_column_info_frozen() -> None:
    col = ColumnInfo(name="id", data_type="INTEGER", is_nullable=False)
    assert col.name == "id"
    assert col.data_type == "INTEGER"
    assert col.is_nullable is False


def test_table_info_with_columns() -> None:
    cols = [
        ColumnInfo(name="id", data_type="INTEGER"),
        ColumnInfo(name="name", data_type="TEXT"),
    ]
    table = TableInfo(table_name="users", columns=cols)
    assert table.table_name == "users"
    assert len(table.columns) == 2


def test_query_request_validation() -> None:
    req = QueryRequest(question="How many users?")
    assert req.question == "How many users?"
    assert req.database == "primary"


def test_approval_request_defaults() -> None:
    req = ApprovalRequest(approved=True)
    assert req.approved is True
    assert req.modified_sql is None


def test_query_record_serialization() -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    data = record.model_dump(mode="json")
    assert data["natural_language"] == "test"
    assert data["approval_status"] == "pending"
    assert data["generated_sql"] == "SELECT 1"
