"use client";

import { useEffect, useRef } from "react";
import { Database } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import type { ChatMessage } from "@/lib/types";

const QUICK_QUESTIONS = [
  "How many artists are in the database?",
  "Top 5 genres by number of tracks",
  "Which customers spent the most money?",
];

interface MessageListProps {
  messages: ChatMessage[];
  onApprovalNeeded: (queryId: string, sql: string, errors: string[]) => void;
  onSendMessage?: (content: string) => void;
}

export function MessageList({ messages, onApprovalNeeded, onSendMessage }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center max-w-sm">
          <Database className="h-10 w-10 mx-auto mb-4 text-muted-foreground/40" />
          <p className="text-lg font-medium text-muted-foreground">
            Ask a question about your data
          </p>
          <p className="mt-1 text-sm text-muted-foreground/60">
            I&apos;ll generate SQL, run it, and explain the results
          </p>
          {onSendMessage && (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {QUICK_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => onSendMessage(q)}
                  className="rounded-full border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-[720px] space-y-4 p-4">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onApprovalNeeded={onApprovalNeeded}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
