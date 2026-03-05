import type { SchemaTable } from "@/hooks/use-schema";
import type { QueryResponse } from "@/lib/types";

const FALLBACK_QUESTIONS = [
  "How many rows are in each table?",
  "Show me the first 5 rows of data",
  "What tables are available?",
];

interface Template {
  generate: (table: SchemaTable) => string;
}

const TEMPLATES: Template[] = [
  { generate: (t) => `How many rows are in ${t.name}?` },
  {
    generate: (t) => {
      const col = t.columns.find(
        (c) =>
          c.type.toLowerCase().includes("int") ||
          c.type.toLowerCase().includes("float") ||
          c.type.toLowerCase().includes("numeric") ||
          c.type.toLowerCase().includes("decimal") ||
          c.type.toLowerCase().includes("real")
      );
      if (col) return `Show the top 5 ${t.name} by ${col.name}`;
      return `Show the first 5 rows from ${t.name}`;
    },
  },
  {
    generate: (t) => {
      const strCol = t.columns.find(
        (c) =>
          c.type.toLowerCase().includes("varchar") ||
          c.type.toLowerCase().includes("text") ||
          c.type.toLowerCase().includes("char")
      );
      if (strCol) return `What are the distinct values of ${strCol.name} in ${t.name}?`;
      return `What columns does ${t.name} have?`;
    },
  },
];

export function generateQuickQuestions(tables?: SchemaTable[]): string[] {
  if (!tables || tables.length === 0) return FALLBACK_QUESTIONS;

  const questions: string[] = [];
  // Shuffle tables for variety
  const shuffled = [...tables].sort(() => Math.random() - 0.5);

  for (const template of TEMPLATES) {
    if (questions.length >= 3) break;
    const table = shuffled[questions.length % shuffled.length];
    questions.push(template.generate(table));
  }

  return questions.slice(0, 3);
}

/**
 * Generate follow-up question suggestions based on the last query result.
 * Extracts column names and result shape to create contextual suggestions.
 */
export function generateFollowUpQuestions(
  lastQuestion: string,
  queryResponse: QueryResponse
): string[] {
  const suggestions: string[] = [];
  const { result, generated_sql, query_type } = queryResponse;

  // Extract table names from SQL (simple regex for FROM/JOIN clauses)
  const tableMatches = generated_sql.match(/(?:FROM|JOIN)\s+([`"']?\w+[`"']?)/gi);
  const tables = tableMatches
    ?.map((m) => m.replace(/(?:FROM|JOIN)\s+/i, "").replace(/[`"']/g, ""))
    .filter((v, i, a) => a.indexOf(v) === i) ?? [];

  if (result && result.length > 0) {
    const columns = Object.keys(result[0]);
    const numericCols = columns.filter((col) =>
      result.every((row) => row[col] == null || typeof row[col] === "number" || !isNaN(Number(row[col])))
    );

    // If results are aggregated, suggest drilling deeper
    if (result.length <= 20 && numericCols.length > 0) {
      const col = numericCols[0];
      suggestions.push(`Break down ${col} by month or category`);
    }

    // If few rows returned, suggest broadening
    if (result.length <= 5 && result.length > 0) {
      suggestions.push(`Show the bottom 5 instead`);
    }

    // If many rows, suggest filtering
    if (result.length > 10) {
      const strCols = columns.filter((c) => !numericCols.includes(c));
      if (strCols.length > 0) {
        suggestions.push(`Filter by a specific ${strCols[0]}`);
      }
    }
  }

  // Analytical queries: suggest summary or comparison
  if (query_type === "analytical") {
    suggestions.push("Summarize the key takeaways");
  }

  // Table-aware suggestions
  if (tables.length > 0) {
    const table = tables[0];
    if (!lastQuestion.toLowerCase().includes("trend")) {
      suggestions.push(`Show trends over time for ${table}`);
    }
  }

  return suggestions.slice(0, 3);
}
