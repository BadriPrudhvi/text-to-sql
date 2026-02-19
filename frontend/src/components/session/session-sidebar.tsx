"use client";

import { MessageSquarePlus, Trash2, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import type { Session } from "@/lib/types";

interface SessionSidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  isCreating: boolean;
  onNewSession: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  isCreating,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
}: SessionSidebarProps) {
  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2">
          <Database className="h-5 w-5 text-sidebar-foreground/70" />
          <span className="text-sm font-semibold">Text to SQL</span>
        </div>
        <Button
          onClick={onNewSession}
          disabled={isCreating}
          className="w-full justify-start gap-2"
          variant="outline"
          size="sm"
        >
          <MessageSquarePlus className="h-4 w-4" />
          {isCreating ? "Creating..." : "New conversation"}
        </Button>
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Conversations</SidebarGroupLabel>
          <SidebarGroupContent>
            {sessions.length === 0 ? (
              <p className="px-2 py-3 text-center text-xs text-sidebar-foreground/50">
                No conversations yet
              </p>
            ) : (
              <SidebarMenu>
                {sessions.map((session) => (
                  <SidebarMenuItem key={session.id}>
                    <SidebarMenuButton
                      isActive={activeSessionId === session.id}
                      onClick={() => onSwitchSession(session.id)}
                      tooltip={session.label}
                    >
                      <span className="truncate">{session.label}</span>
                    </SidebarMenuButton>
                    <SidebarMenuAction
                      showOnHover
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                    >
                      <Trash2 className="text-sidebar-foreground/50 hover:text-destructive" />
                    </SidebarMenuAction>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
