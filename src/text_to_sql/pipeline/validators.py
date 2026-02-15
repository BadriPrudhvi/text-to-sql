from __future__ import annotations

import re
from typing import Any


class ResultValidator:
    """Validates query results for common issues that suggest the SQL may be incorrect."""

    _AMOUNT_COLUMNS = {"count", "total", "amount", "price", "age", "quantity", "sum", "avg"}

    def validate(
        self, sql: str, result: list[dict[str, Any]] | None, question: str
    ) -> list[str]:
        warnings: list[str] = []

        if result is None:
            return warnings

        warnings.extend(self._check_empty_aggregate(sql, result))
        warnings.extend(self._check_suspicious_negatives(result))
        warnings.extend(self._check_limit_mismatch(sql, result, question))

        return warnings

    def _check_empty_aggregate(
        self, sql: str, result: list[dict[str, Any]]
    ) -> list[str]:
        """Aggregate queries (COUNT/SUM/AVG) returning no rows may indicate wrong filters."""
        sql_upper = sql.upper()
        has_aggregate = any(fn in sql_upper for fn in ("COUNT(", "SUM(", "AVG(", "MIN(", "MAX("))
        if has_aggregate and len(result) == 0:
            return [
                "Aggregate query returned no results — table may be empty or filter too restrictive"
            ]
        return []

    def _check_suspicious_negatives(self, result: list[dict[str, Any]]) -> list[str]:
        """Flag unexpected negative values in columns that should be non-negative."""
        if not result:
            return []

        for col_name in result[0]:
            if col_name.lower() not in self._AMOUNT_COLUMNS:
                continue
            for row in result:
                val = row.get(col_name)
                if isinstance(val, (int, float)) and val < 0:
                    return [f"Unexpected negative value in column '{col_name}'"]
        return []

    def _check_limit_mismatch(
        self, sql: str, result: list[dict[str, Any]], question: str
    ) -> list[str]:
        """Check if user asked for 'top N' but LIMIT doesn't match."""
        match = re.search(r"top\s+(\d+)", question.lower())
        if not match:
            return []

        requested = int(match.group(1))
        limit_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_match:
            actual_limit = int(limit_match.group(1))
            if actual_limit != requested and len(result) > requested:
                return [
                    f"User asked for top {requested} but query returned {len(result)} rows"
                ]
        return []
