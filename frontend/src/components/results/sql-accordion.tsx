"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, Check } from "lucide-react";
import { format as formatSQL } from "sql-formatter";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";

interface SQLAccordionProps {
  sql: string;
}

export function SQLAccordion({ sql }: SQLAccordionProps) {
  const [copied, setCopied] = useState(false);
  const [highlighted, setHighlighted] = useState("");

  const formattedSQL = useMemo(() => {
    try {
      return formatSQL(sql, {
        language: "sql",
        tabWidth: 2,
        keywordCase: "upper",
      });
    } catch {
      return sql;
    }
  }, [sql]);

  useEffect(() => {
    let cancelled = false;
    import("shiki").then(({ codeToHtml }) => {
      codeToHtml(formattedSQL, {
        lang: "sql",
        theme: "github-light",
      }).then((html) => {
        if (!cancelled) setHighlighted(html);
      });
    });
    return () => {
      cancelled = true;
    };
  }, [formattedSQL]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!sql) return null;

  // shiki generates sanitized HTML from code — safe to render
  return (
    <Accordion type="single" collapsible className="w-full">
      <AccordionItem value="sql" className="border rounded-md">
        <AccordionTrigger className="px-3 py-2 text-xs hover:no-underline">
          <span className="font-mono text-muted-foreground">SQL Query</span>
        </AccordionTrigger>
        <AccordionContent className="px-3 pb-3">
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-1 right-1 h-7 w-7"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-600" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
            {highlighted ? (
              <div
                className="overflow-x-auto rounded bg-muted/50 p-3 text-sm [&_pre]:!bg-transparent [&_code]:!bg-transparent"
                dangerouslySetInnerHTML={{ __html: highlighted }}
              />
            ) : (
              <pre className="overflow-x-auto rounded bg-muted/50 p-3 text-sm font-mono whitespace-pre-wrap">
                {formattedSQL}
              </pre>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
