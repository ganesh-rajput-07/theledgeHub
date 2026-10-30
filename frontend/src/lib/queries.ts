"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AuditEntry,
  ChatMessage,
  Conversation,
  DocumentItem,
  Me,
  Member,
  Organization,
  Provider,
  Workspace,
} from "@/types/api";

export const keys = {
  me: ["me"] as const,
  orgs: ["orgs"] as const,
  workspaces: (orgId: string) => ["orgs", orgId, "workspaces"] as const,
  members: (orgId: string) => ["orgs", orgId, "members"] as const,
  audit: (orgId: string) => ["orgs", orgId, "audit"] as const,
  providers: (orgId: string) => ["orgs", orgId, "providers"] as const,
  workspace: (id: string) => ["workspaces", id] as const,
  documents: (wsId: string) => ["workspaces", wsId, "documents"] as const,
  conversations: (wsId: string) => ["workspaces", wsId, "conversations"] as const,
  messages: (conversationId: string) => ["conversations", conversationId, "messages"] as const,
};

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api<Me>("auth/me") });

export const useOrganizations = () =>
  useQuery({ queryKey: keys.orgs, queryFn: () => api<Organization[]>("organizations") });

export const useWorkspaces = (orgId: string | undefined) =>
  useQuery({
    queryKey: keys.workspaces(orgId ?? ""),
    queryFn: () => api<Workspace[]>(`organizations/${orgId}/workspaces`),
    enabled: !!orgId,
  });

export const useWorkspace = (id: string | undefined) =>
  useQuery({ queryKey: keys.workspace(id ?? ""), queryFn: () => api<Workspace>(`workspaces/${id}`), enabled: !!id });

export const useMembers = (orgId: string) =>
  useQuery({ queryKey: keys.members(orgId), queryFn: () => api<Member[]>(`organizations/${orgId}/members`) });

export const useProviders = (orgId: string | undefined) =>
  useQuery({
    queryKey: keys.providers(orgId ?? ""),
    queryFn: () => api<Provider[]>(`organizations/${orgId}/providers`),
    enabled: !!orgId,
  });

export const useDocuments = (wsId: string) =>
  useQuery({
    queryKey: keys.documents(wsId),
    queryFn: () => api<DocumentItem[]>(`workspaces/${wsId}/documents`),
    // Poll while anything is still being ingested, then stop.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === "pending" || d.status === "processing") ? 2000 : false,
  });

export const useConversations = (wsId: string) =>
  useQuery({
    queryKey: keys.conversations(wsId),
    queryFn: () => api<Conversation[]>(`workspaces/${wsId}/conversations`),
  });

export const useMessages = (conversationId: string | null) =>
  useQuery({
    queryKey: keys.messages(conversationId ?? ""),
    queryFn: () => api<ChatMessage[]>(`conversations/${conversationId}/messages`),
    enabled: !!conversationId,
  });

export const useAuditLog = (orgId: string, enabled: boolean) =>
  useQuery({
    queryKey: keys.audit(orgId),
    queryFn: () => api<AuditEntry[]>(`organizations/${orgId}/audit-logs?limit=50`),
    enabled,
  });
