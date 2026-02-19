"""Prompts for multi-agent analytical query pipeline."""

from __future__ import annotations

CLASSIFICATION_PROMPT = """\
Classify the following user question as either "simple" or "analytical".

**simple**: Direct data retrieval — counts, lists, lookups, single aggregations.
Examples: "How many users are there?", "List all orders from last month", "Show me the top 5 products"

**analytical**: Requires multi-step analysis, comparisons, trends, recommendations, or planning.
Signal words: analyze, compare, trend, recommend, why, correlate, optimize, increase, decrease, improve, forecast, breakdown, relationship.
Examples: "Analyze sales data and recommend ways to increase revenue", "Compare performance across regions and identify underperformers", "What factors correlate with customer churn?"

When in doubt, classify as "simple".

User question: {question}"""

PLANNER_PROMPT = """\
You are a data analyst planning a multi-step SQL analysis.

Given the database schema and user question, create an ordered analysis plan.
Each step should produce one SQL query that builds toward answering the question.
Steps can reference insights from previous steps.

Rules:
- Maximum {max_plan_steps} steps
- Each step must be independently executable as a single SQL query
- Order steps from foundational data gathering to deeper analysis
- Include steps for different dimensions (time, category, segment) when relevant
- The final synthesis will combine all step results into a cohesive answer

Database schema:
{schema_context}

User question: {question}"""

STEP_SQL_PROMPT = """\
Generate a single SQL query for this analysis step.

Database dialect: {dialect}
Step description: {step_description}
SQL hint: {sql_hint}

Database schema:
{schema_context}

{previous_results_context}

Rules:
- Return ONLY the raw SQL query, nothing else
- Do NOT include any explanation, commentary, or description after the SQL
- Do NOT include markdown code fences
- The query must be a SELECT statement
- Use appropriate aggregations, grouping, and ordering
- Limit results to a reasonable number of rows (use LIMIT if needed)
- The query must be valid {dialect} SQL"""

ANALYST_PROMPT = """\
You are a data analyst synthesizing results from a multi-step analysis.

User question: {question}

Analysis results:
{results_context}

Instructions:
- Present key findings with specific numbers from the data
- Identify cross-cutting insights that span multiple analysis steps
- If some steps failed, acknowledge limitations but still provide insights from available data
- Be concise and direct — answer the user's question without adding unsolicited recommendations"""
