"use client";

import { useCallback, useEffect, useState } from "react";
import { createSession } from "@/lib/api";
import type { Session } from "@/lib/types";

const STORAGE_KEY = "text-to-sql-sessions";

function loadSessions(): Session[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return (JSON.parse(raw) as Session[]).map((s) => ({
      ...s,
      createdAt: new Date(s.createdAt),
    }));
  } catch {
    return [];
  }
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

export function useSession() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  const newSession = useCallback(async () => {
    setIsCreating(true);
    try {
      const { session_id } = await createSession();
      const session: Session = {
        id: session_id,
        label: "New conversation",
        createdAt: new Date(),
      };
      setSessions((prev) => {
        const next = [session, ...prev];
        saveSessions(next);
        return next;
      });
      setActiveSessionId(session_id);
      return session_id;
    } finally {
      setIsCreating(false);
    }
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const updateSessionLabel = useCallback((id: string, label: string) => {
    setSessions((prev) => {
      const next = prev.map((s) =>
        s.id === id ? { ...s, label: label.slice(0, 50) } : s
      );
      saveSessions(next);
      return next;
    });
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      saveSessions(next);
      return next;
    });
    setActiveSessionId((prev) => (prev === id ? null : prev));
  }, []);

  return {
    sessions,
    activeSessionId,
    isCreating,
    newSession,
    switchSession,
    updateSessionLabel,
    deleteSession,
  };
}
