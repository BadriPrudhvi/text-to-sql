"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSessionHistory } from "@/lib/api";
import type { ChatMessage, QueryResponse } from "@/lib/types";
import { useSSEStream } from "./use-sse-stream";

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const stream = useSSEStream();
  const prevSessionRef = useRef<string | null>(null);
  const sendingRef = useRef(false);

  // Load history when session changes
  useEffect(() => {
    if (!sessionId || sessionId === prevSessionRef.current) return;
    prevSessionRef.current = sessionId;

    let cancelled = false;
    setIsLoadingHistory(true);

    getSessionHistory(sessionId)
      .then((history) => {
        if (cancelled) return;
        const loaded: ChatMessage[] = [];
        for (const q of history.queries) {
          loaded.push({
            id: `user-${q.id}`,
            role: "user",
            content: q.natural_language as string,
            timestamp: new Date(q.created_at as string),
          });
          loaded.push({
            id: `assistant-${q.id}`,
            role: "assistant",
            content: (q.answer as string) || "",
            timestamp: new Date(
              (q.executed_at as string) ||
                (q.created_at as string)
            ),
            queryResponse: q as unknown as QueryResponse,
          });
        }
        setMessages(loaded);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Update streaming message as pipeline progresses
  useEffect(() => {
    if (!stream.isStreaming && !stream.finalResponse) return;

    setMessages((prev) => {
      const copy = [...prev];
      const lastIdx = copy.length - 1;
      if (lastIdx < 0 || copy[lastIdx].role !== "assistant") return prev;

      if (stream.finalResponse) {
        copy[lastIdx] = {
          ...copy[lastIdx],
          content: stream.finalResponse.answer || "",
          pipelineSteps: stream.pipelineSteps,
          queryResponse: stream.finalResponse,
          isStreaming: false,
          error: stream.error || undefined,
        };
      } else {
        copy[lastIdx] = {
          ...copy[lastIdx],
          pipelineSteps: stream.pipelineSteps,
          isStreaming: true,
          error: stream.error || undefined,
        };
      }
      return copy;
    });
  }, [stream.pipelineSteps, stream.finalResponse, stream.isStreaming, stream.error]);

  const sendMessage = useCallback(
    (content: string, sessionIdOverride?: string) => {
      const sid = sessionIdOverride || sessionId;
      if (!sid || stream.isStreaming || sendingRef.current) return;
      sendingRef.current = true;

      // Mark session as seen so history effect doesn't overwrite our messages
      prevSessionRef.current = sid;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date(),
      };

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        pipelineSteps: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      stream.startStream(sid, content);
    },
    [sessionId, stream]
  );

  // Reset send guard when streaming starts
  useEffect(() => {
    if (stream.isStreaming) {
      sendingRef.current = false;
    }
  }, [stream.isStreaming]);

  // Update assistant message after approval
  const updateLastAssistantMessage = useCallback(
    (updates: Partial<ChatMessage>) => {
      setMessages((prev) => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === "assistant") {
            copy[i] = { ...copy[i], ...updates };
            break;
          }
        }
        return copy;
      });
    },
    []
  );

  return {
    messages,
    isLoadingHistory,
    isStreaming: stream.isStreaming,
    sendMessage,
    updateLastAssistantMessage,
    stopStream: stream.stopStream,
  };
}
