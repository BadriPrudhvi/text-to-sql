"use client";

import { Database } from "lucide-react";

interface SourceTablesProps {
  sql: string;
}

function extractTableNames(sql: string): string[] {
  // Match table names after FROM and JOIN keywords
  const pattern = /(?:FROM|JOIN)\s+([`"']?[\w.]+[`"']?)/gi;
  const tables: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(sql)) !== null) {
    const name = match[1].replace(/[`"']/g, "");
    // Skip subquery aliases and common SQL keywords
    if (!["select", "where", "on", "and", "or"].includes(name.toLowerCase())) {
      tables.push(name);
    }
  }

  // Deduplicate
  return [...new Set(tables)];
}

export function SourceTables({ sql }: SourceTablesProps) {
  const tables = extractTableNames(sql);
  if (tables.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <Database className="h-3 w-3 text-muted-foreground/50 shrink-0" />
      {tables.map((table) => (
        <span
          key={table}
          className="inline-flex items-center rounded-full bg-muted/60 border border-border/50 px-2 py-0.5 text-[11px] text-muted-foreground font-mono transition-all duration-200 hover:scale-105 hover:bg-muted hover:border-border hover:text-foreground cursor-default"
        >
          {table}
        </span>
      ))}
    </div>
  );
}
