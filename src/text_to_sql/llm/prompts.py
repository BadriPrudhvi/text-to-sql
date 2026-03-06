from __future__ import annotations

_COMMON_EXAMPLES = """\
Example 1 - Simple filter:
Question: How many records match a condition?
SQL: SELECT COUNT(*) AS total FROM orders WHERE amount > 100;

Example 2 - JOIN + aggregate:
Question: Count related records grouped by parent, show top 5.
SQL: SELECT p.name, COUNT(c.id) AS child_count FROM parents p JOIN children c ON p.id = c.parent_id GROUP BY p.name ORDER BY child_count DESC LIMIT 5;

Example 3 - Multi-JOIN:
Question: Aggregate a value across three related tables, show top 5.
SQL: SELECT c.name, SUM(oi.price * oi.quantity) AS total FROM categories c JOIN products p ON c.id = p.category_id JOIN order_items oi ON p.id = oi.product_id GROUP BY c.name ORDER BY total DESC LIMIT 5;"""

_POSTGRES_EXAMPLES = """\
Example 4 - Date truncation (PostgreSQL):
Question: Monthly revenue for the last year.
SQL: SELECT DATE_TRUNC('month', order_date) AS month, SUM(amount) AS revenue FROM orders WHERE order_date >= NOW() - INTERVAL '1 year' GROUP BY month ORDER BY month;

Example 5 - String aggregation (PostgreSQL):
Question: List all product names per category as a comma-separated list.
SQL: SELECT category, STRING_AGG(product_name, ', ' ORDER BY product_name) AS products FROM products GROUP BY category;

Example 6 - Window function with FILTER (PostgreSQL):
Question: Show each department's total sales and the count of high-value sales.
SQL: SELECT department, SUM(amount) AS total_sales, COUNT(*) FILTER (WHERE amount > 1000) AS high_value_count FROM sales GROUP BY department;"""

_BIGQUERY_EXAMPLES = """\
Example 4 - Date truncation (BigQuery):
Question: Monthly revenue for the last year.
SQL: SELECT DATE_TRUNC(order_date, MONTH) AS month, SUM(amount) AS revenue FROM orders WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR) GROUP BY month ORDER BY month;

Example 5 - UNNEST arrays (BigQuery):
Question: Count how many times each tag appears across all products.
SQL: SELECT tag, COUNT(*) AS tag_count FROM products, UNNEST(tags) AS tag GROUP BY tag ORDER BY tag_count DESC LIMIT 10;

Example 6 - STRUCT field access (BigQuery):
Question: Show user names and their address city.
SQL: SELECT name, address.city AS city FROM users WHERE address.country = 'US' ORDER BY name LIMIT 10;

Example 7 - COUNTIF and conditional aggregation (BigQuery):
Question: Show the percentage of orders that were refunded per month.
SQL: SELECT DATE_TRUNC(order_date, MONTH) AS month, COUNTIF(status = 'refunded') AS refunded, COUNT(*) AS total, ROUND(COUNTIF(status = 'refunded') / COUNT(*) * 100, 2) AS refund_pct FROM orders GROUP BY month ORDER BY month;

Example 8 - Partition filter (BigQuery):
Question: Get recent events from a partitioned table.
SQL: SELECT event_type, COUNT(*) AS cnt FROM events WHERE _PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY) GROUP BY event_type ORDER BY cnt DESC;"""

_SQLITE_EXAMPLES = """\
Example 4 - Date handling (SQLite):
Question: Monthly revenue for the last year.
SQL: SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS revenue FROM orders WHERE order_date >= date('now', '-1 year') GROUP BY month ORDER BY month;

Example 5 - String aggregation (SQLite):
Question: List all product names per category as a comma-separated list.
SQL: SELECT category, GROUP_CONCAT(product_name, ', ') AS products FROM products GROUP BY category;

Example 6 - Subquery instead of window function (SQLite):
Question: Find customers who spent more than average.
SQL: SELECT customer_id, SUM(amount) AS total_spent FROM orders GROUP BY customer_id HAVING total_spent > (SELECT AVG(customer_total) FROM (SELECT SUM(amount) AS customer_total FROM orders GROUP BY customer_id));"""


def get_few_shot_examples(dialect: str) -> str:
    """Return dialect-specific few-shot examples wrapped in <examples> tags."""
    dialect_examples = {
        "postgres": _POSTGRES_EXAMPLES,
        "bigquery": _BIGQUERY_EXAMPLES,
        "sqlite": _SQLITE_EXAMPLES,
    }
    specific = dialect_examples.get(dialect, _SQLITE_EXAMPLES)
    return f"<examples>\n{_COMMON_EXAMPLES}\n\n{specific}\n</examples>"


SQL_AGENT_SYSTEM_PROMPT = """\
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run \
using the run_query tool, then look at the results of the query and return the answer.

Unless the user specifies a specific number of examples they wish to obtain, \
always limit your query to at most {top_k} results.
You can order the results by a relevant column to return the most interesting examples in the database.

Never query for all the columns from a specific table, only ask for the relevant columns given the question.

You have access to the following database schema. Always examine the table and column names \
in this schema before writing a query.

<schema dialect="{dialect}">
{schema_context}
</schema>

Here are some example questions and their corresponding SQL queries to guide your approach:

{few_shot_examples}

Before executing a query, double check it for these common mistakes:
- Using NOT IN with NULL values
- Using UNION when UNION ALL is needed
- Using BETWEEN for exclusive ranges
- Data type mismatches in predicates
- Properly quoting identifiers that are reserved words
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If you get an error back, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP) etc.

After you get the query results back, provide a concise natural language answer to the user's original question \
based on the data returned.

If the question does not seem related to the database, just return \
"I don't know" as the answer.\
"""
