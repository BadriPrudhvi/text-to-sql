import type { SchemaTable } from "@/hooks/use-schema";

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
