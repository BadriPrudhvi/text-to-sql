"use client";

import { useEffect, useRef } from "react";
import { Database } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./message-bubble";
import { generateQuickQuestions, generateFollowUpQuestions } from "@/lib/quick-questions";
import type { ChatMessage } from "@/lib/types";
import type { SchemaTable } from "@/hooks/use-schema";

interface MessageListProps {
  messages: ChatMessage[];
  onApprovalNeeded: (queryId: string, sql: string, errors: string[]) => void;
  onSendMessage?: (content: string) => void;
  tables?: SchemaTable[];
}

export function MessageList({ messages, onApprovalNeeded, onSendMessage, tables }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    const questions = generateQuickQuestions(tables);
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
              {questions.map((q, i) => (
                <motion.button
                  key={q}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: i * 0.08 }}
                  onClick={() => onSendMessage(q)}
                  className="rounded-full border border-violet-300/40 bg-violet-50 px-3 py-1.5 text-xs text-violet-700 hover:bg-violet-100 hover:border-violet-300/60 dark:border-violet-400/20 dark:bg-violet-500/10 dark:text-violet-300 dark:hover:bg-violet-500/20 dark:hover:border-violet-400/30 transition-colors"
                >
                  {q}
                </motion.button>
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
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              <MessageBubble
                message={msg}
                onApprovalNeeded={onApprovalNeeded}
              />
            </motion.div>
          ))}
        </AnimatePresence>
        <FollowUpPills messages={messages} onSend={onSendMessage} />
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

function FollowUpPills({
  messages,
  onSend,
}: {
  messages: ChatMessage[];
  onSend?: (content: string) => void;
}) {
  if (!onSend || messages.length === 0) return null;

  // Hide while any message is streaming
  if (messages.some((m) => m.isStreaming)) return null;

  // Find last assistant message that is done streaming and has a query response
  const lastAssistant = [...messages].reverse().find(
    (m) => m.role === "assistant" && !m.isStreaming && m.queryResponse
  );
  if (!lastAssistant?.queryResponse) return null;

  // Find the user question that preceded it
  const assistantIdx = messages.indexOf(lastAssistant);
  const userMsg = messages
    .slice(0, assistantIdx)
    .reverse()
    .find((m) => m.role === "user");

  const followUps = generateFollowUpQuestions(
    userMsg?.content ?? "",
    lastAssistant.queryResponse
  );
  if (followUps.length === 0) return null;

  return (
    <motion.div
      className="flex flex-wrap gap-2 pt-1 pb-2"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: 0.3 }}
    >
      {followUps.map((q, i) => (
        <motion.button
          key={q}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2, delay: 0.35 + i * 0.06 }}
          onClick={() => onSend(q)}
          className="rounded-full border border-violet-300/40 bg-violet-50 px-3 py-1.5 text-xs text-violet-700 hover:bg-violet-100 hover:border-violet-300/60 dark:border-violet-400/20 dark:bg-violet-500/10 dark:text-violet-300 dark:hover:bg-violet-500/20 dark:hover:border-violet-400/30 transition-colors"
        >
          {q}
        </motion.button>
      ))}
    </motion.div>
  );
}
