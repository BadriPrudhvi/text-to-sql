"use client";

import { User, Bot, AlertCircle, CheckCircle2 } from "lucide-react";
import { PipelineStepper } from "@/components/pipeline/pipeline-stepper";
import { SQLAccordion } from "@/components/results/sql-accordion";
import { DataTable } from "@/components/results/data-table";
import { AnswerCard } from "@/components/results/answer-card";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { QueryTypeBadge } from "@/components/ui/query-type-badge";

interface MessageBubbleProps {
  message: ChatMessage;
  onApprovalNeeded?: (queryId: string, sql: string, errors: string[]) => void;
}

export function MessageBubble({ message, onApprovalNeeded }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-background">
          <Bot className="h-4 w-4" />
        </div>
      )}

      <div
        className={cn(
          "max-w-[600px] rounded-lg px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "border bg-background"
        )}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <AssistantContent message={message} onApprovalNeeded={onApprovalNeeded} />
        )}
      </div>

      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
          <User className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}

function AssistantContent({
  message,
  onApprovalNeeded,
}: {
  message: ChatMessage;
  onApprovalNeeded?: (queryId: string, sql: string, errors: string[]) => void;
}) {
  const { pipelineSteps, queryResponse, isStreaming, error } = message;

  // Show pipeline stepper if we have steps
  if (pipelineSteps && pipelineSteps.length > 0) {
    const needsApproval =
      queryResponse?.approval_status === "pending" &&
      queryResponse.validation_errors.length > 0;

    return (
      <div className="space-y-3">
        <PipelineStepper
          steps={pipelineSteps}
          isStreaming={!!isStreaming}
          analysisSteps={queryResponse?.analysis_steps}
        />

        {error && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {needsApproval && onApprovalNeeded && (
          <button
            onClick={() =>
              onApprovalNeeded(
                queryResponse.query_id,
                queryResponse.generated_sql,
                queryResponse.validation_errors
              )
            }
            className="text-sm font-medium text-amber-600 hover:text-amber-700 underline underline-offset-2"
          >
            Review and approve SQL
          </button>
        )}

        {queryResponse?.generated_sql &&
          queryResponse.approval_status !== "pending" &&
          queryResponse.query_type !== "analytical" && (
            <SQLAccordion sql={queryResponse.generated_sql} />
          )}

        {queryResponse?.result && queryResponse.result.length > 0 && (
          <DataTable data={queryResponse.result} />
        )}

        {queryResponse?.answer && <AnswerCard answer={queryResponse.answer} />}

        {queryResponse?.error && queryResponse.approval_status === "failed" && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <p>{queryResponse.error}</p>
          </div>
        )}

        {queryResponse?.approval_status === "rejected" && (
          <p className="text-sm text-muted-foreground italic">
            Query was rejected.
          </p>
        )}
      </div>
    );
  }

  // Response without pipeline steps (from history or when steps were lost)
  if (queryResponse) {
    return (
      <div className="space-y-3">
        {/* Compact completed indicator + query type badge */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-md bg-emerald-50 px-2.5 py-1.5 text-xs text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span className="font-medium">Completed</span>
          </div>
          {queryResponse.query_type && (
            <QueryTypeBadge queryType={queryResponse.query_type} />
          )}
        </div>

        {queryResponse.generated_sql && (
          <SQLAccordion sql={queryResponse.generated_sql} />
        )}
        {queryResponse.result && queryResponse.result.length > 0 && (
          <DataTable data={queryResponse.result} />
        )}
        {queryResponse.answer && <AnswerCard answer={queryResponse.answer} />}
        {queryResponse.error && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <p>{queryResponse.error}</p>
          </div>
        )}
      </div>
    );
  }

  if (message.content) {
    return <p className="text-sm whitespace-pre-wrap">{message.content}</p>;
  }

  // Animated thinking dots before any pipeline steps arrive
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-muted-foreground/60" />
      <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-muted-foreground/60" />
      <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-muted-foreground/60" />
    </div>
  );
}
