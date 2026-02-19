"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { approveQuery } from "@/lib/api";
import type { ApprovalResponse } from "@/lib/types";

interface ApprovalDialogProps {
  open: boolean;
  onClose: () => void;
  queryId: string;
  sql: string;
  validationErrors: string[];
  onResult: (result: ApprovalResponse) => void;
}

export function ApprovalDialog({
  open,
  onClose,
  queryId,
  sql,
  validationErrors,
  onResult,
}: ApprovalDialogProps) {
  const [editedSql, setEditedSql] = useState(sql);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync editedSql when dialog opens with new SQL
  useEffect(() => {
    setEditedSql(sql);
  }, [sql]);

  const handleApprove = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const modified = editedSql.trim() !== sql.trim() ? editedSql : undefined;
      const result = await approveQuery(queryId, true, modified);
      onResult(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await approveQuery(queryId, false);
      onResult(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            SQL Approval Required
          </DialogTitle>
          <DialogDescription>
            The generated SQL has validation issues. Review and optionally edit
            before approving.
          </DialogDescription>
        </DialogHeader>

        {validationErrors.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {validationErrors.map((err, i) => (
              <Badge key={i} variant="destructive" className="text-xs">
                {err}
              </Badge>
            ))}
          </div>
        )}

        <div>
          <label className="text-sm font-medium">SQL Query</label>
          <Textarea
            value={editedSql}
            onChange={(e) => setEditedSql(e.target.value)}
            className="mt-1.5 min-h-[120px] font-mono text-sm"
            disabled={isSubmitting}
          />
        </div>

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        <DialogFooter>
          <Button
            variant="destructive"
            onClick={handleReject}
            disabled={isSubmitting}
          >
            Reject
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {isSubmitting ? "Submitting..." : "Approve & Execute"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
