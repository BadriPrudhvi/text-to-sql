"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SessionSidebar } from "@/components/session/session-sidebar";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import { ApprovalDialog } from "@/components/approval/approval-dialog";
import { HealthDot } from "@/components/health-dot";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useSession } from "@/hooks/use-session";
import { useChat } from "@/hooks/use-chat";
import type { ApprovalResponse, QueryResponse } from "@/lib/types";

export function ChatPage() {
  const {
    sessions,
    activeSessionId,
    isCreating,
    newSession,
    switchSession,
    updateSessionLabel,
    deleteSession,
  } = useSession();

  const {
    messages,
    isStreaming,
    sendMessage,
    updateLastAssistantMessage,
  } = useChat(activeSessionId);

  // Approval dialog state
  const [approvalState, setApprovalState] = useState<{
    open: boolean;
    queryId: string;
    sql: string;
    errors: string[];
  }>({ open: false, queryId: "", sql: "", errors: [] });

  // Update session label once after first user message
  const labelledSessionRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeSessionId || labelledSessionRef.current === activeSessionId) return;
    const firstUserMsg = messages.find((m) => m.role === "user");
    if (firstUserMsg) {
      labelledSessionRef.current = activeSessionId;
      updateSessionLabel(activeSessionId, firstUserMsg.content);
    }
  }, [messages, activeSessionId, updateSessionLabel]);

  const handleSend = useCallback(
    async (content: string) => {
      let sid = activeSessionId;
      if (!sid) {
        sid = await newSession();
      }
      if (sid) sendMessage(content, sid);
    },
    [activeSessionId, newSession, sendMessage]
  );

  const handleApprovalNeeded = useCallback(
    (queryId: string, sql: string, errors: string[]) => {
      setApprovalState({ open: true, queryId, sql, errors });
    },
    []
  );

  const handleApprovalResult = useCallback(
    (result: ApprovalResponse) => {
      updateLastAssistantMessage({
        queryResponse: {
          query_id: result.query_id,
          question: "",
          generated_sql: approvalState.sql,
          validation_errors: [],
          approval_status: result.approval_status,
          message: "",
          result: result.result,
          answer: result.answer,
          error: result.error,
          query_type: "simple",
          analysis_plan: null,
          analysis_steps: null,
        } as QueryResponse,
        content: result.answer || "",
      });
    },
    [updateLastAssistantMessage, approvalState.sql]
  );

  return (
    <SidebarProvider>
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        isCreating={isCreating}
        onNewSession={newSession}
        onSwitchSession={switchSession}
        onDeleteSession={deleteSession}
      />
      <SidebarInset>
        {/* Header */}
        <header className="flex h-12 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 !h-4" />
          <div className="flex-1" />
          <HealthDot />
        </header>

        {/* Messages */}
        <MessageList
          messages={messages}
          onApprovalNeeded={handleApprovalNeeded}
          onSendMessage={handleSend}
        />

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          disabled={isStreaming}
          placeholder={
            activeSessionId
              ? "Ask a question about your data..."
              : "Ask a question to start a new conversation..."
          }
        />
      </SidebarInset>

      {/* Approval dialog */}
      <ApprovalDialog
        open={approvalState.open}
        onClose={() => setApprovalState((s) => ({ ...s, open: false }))}
        queryId={approvalState.queryId}
        sql={approvalState.sql}
        validationErrors={approvalState.errors}
        onResult={handleApprovalResult}
      />
    </SidebarProvider>
  );
}
