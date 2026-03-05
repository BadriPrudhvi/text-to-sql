"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Copy, Check } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AnswerCardProps {
  answer: string;
  /** When true, suppress markdown tables (avoids duplicate when DataTable is already shown) */
  hideTable?: boolean;
}

export function AnswerCard({ answer, hideTable }: AnswerCardProps) {
  const [copied, setCopied] = useState(false);

  if (!answer) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      className="prose-sm max-w-none relative"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <button
        onClick={handleCopy}
        className="absolute top-0 right-0 rounded-md p-1 text-muted-foreground/50 hover:text-foreground hover:bg-muted transition-colors"
        title="Copy answer"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-emerald-600" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="text-sm leading-relaxed mb-3 last:mb-0">{children}</p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          h1: ({ children }) => (
            <h1 className="text-base font-semibold mb-2 mt-4 first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-semibold mb-2 mt-3.5 first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium mb-1.5 mt-3 first:mt-0">{children}</h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 text-sm mb-3 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 text-sm mb-3 space-y-1">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          code: ({ children }) => (
            <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">
              {children}
            </code>
          ),
          hr: () => <hr className="my-3 border-border" />,
          table: hideTable ? () => null : ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-md border">
              <table className="w-full text-xs">{children}</table>
            </div>
          ),
          thead: hideTable ? () => null : ({ children }) => (
            <thead className="bg-muted/50 border-b">{children}</thead>
          ),
          tbody: hideTable ? () => null : ({ children }) => <tbody className="divide-y">{children}</tbody>,
          tr: hideTable ? () => null : ({ children }) => <tr>{children}</tr>,
          th: hideTable ? () => null : ({ children }) => (
            <th className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">
              {children}
            </th>
          ),
          td: hideTable ? () => null : ({ children }) => (
            <td className="px-3 py-2 whitespace-nowrap">{children}</td>
          ),
        }}
      >
        {answer}
      </Markdown>
    </motion.div>
  );
}
