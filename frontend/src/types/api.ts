// Mirrors the FastAPI response schemas (backend/app/schemas).

export type Role = "owner" | "admin" | "member";

export interface Me {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
  organizations: { organization_id: string; organization_name: string; role: Role }[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: Role;
  created_at: string;
}

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string | null;
  role: Role;
  created_at: string;
}

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export interface DocumentItem {
  id: string;
  filename: string;
  mime_type: string | null;
  file_size: number | null;
  checksum: string | null;
  status: DocumentStatus;
  page_count: number | null;
  embedding_model: string | null;
  created_at: string;
}

export interface DocumentStatusInfo {
  document_id: string;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
}

export type ProviderName = "openai" | "anthropic" | "gemini" | "ollama" | "mock";

export interface Provider {
  id: string;
  provider: ProviderName;
  label: string;
  key_hint: string | null;
  base_url: string | null;
  default_model: string;
  is_active: boolean;
  last_validated_at: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  provider_credential_id: string | null;
  model: string;
  document_ids: string[];
  created_at: string;
}

export interface Citation {
  citation_id: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  quoted_text: string;
  score: number | null;
}

export interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  status: "completed" | "not_found" | null;
  grounded: boolean | null;
  citations: Citation[];
  model: string | null;
  usage: { input_tokens: number | null; output_tokens: number | null } | null;
  latency_ms: number | null;
  search_query: string | null;
  created_at: string;
}

export interface Answer {
  message_id: string;
  answer: string;
  status: "completed" | "not_found";
  grounded: boolean;
  citations: Citation[];
  model: string | null;
  usage: { input_tokens: number | null; output_tokens: number | null };
  latency_ms: number;
  truncated: boolean;
  search_query: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  user_id: string | null;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}
