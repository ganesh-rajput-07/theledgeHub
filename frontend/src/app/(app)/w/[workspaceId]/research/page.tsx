"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, KeyRound, MessageSquarePlus, SearchX, Send, Sparkles, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { AnswerMarkdown } from "@/components/answer-markdown";
import { Badge, Button, EmptyState, ErrorText, Field, Input, Select, Spinner } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";
import { keys, useConversations, useDocuments, useMessages, useProviders, useWorkspace } from "@/lib/queries";
import type { Answer, ChatMessage, Citation, Conversation } from "@/types/api";

// ---------------------------------------------------------------- left: history + new conversation

function NewConversation({ workspaceId, orgId, onCreated }: { workspaceId: string; orgId?: string; onCreated: (c: Conversation) => void }) {
  const queryClient = useQueryClient();
  const { data: providers } = useProviders(orgId);
  const { data: documents } = useDocuments(workspaceId);
  const ready = documents?.filter((d) => d.status === "completed") ?? [];
  const active = providers?.filter((p) => p.is_active) ?? [];

  const create = useMutation({
    mutationFn: (payload: { provider_id: string; model?: string; document_ids: string[] }) =>
      api<Conversation>(`workspaces/${workspaceId}/conversations`, { method: "POST", json: payload }),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
      onCreated(conversation);
    },
  });

  if (providers && active.length === 0) {
    return (
      <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-800">
        <KeyRound className="mb-1 size-4" />
        No AI provider connected.{" "}
        <Link href={`/org/${orgId}/settings`} className="font-medium underline">
          Add your API key
        </Link>{" "}
        (an owner or admin can do this).
      </div>
    );
  }

  return (
    <form
      className="space-y-3 rounded-md bg-slate-50 p-3 ring-1 ring-slate-200"
      onSubmit={(e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        create.mutate({
          provider_id: String(form.get("provider_id")),
          model: String(form.get("model") || "") || undefined,
          document_ids: form.getAll("document_ids").map(String),
        });
      }}
    >
      <Field label="AI provider">
        <Select name="provider_id" required>
          {active.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} · {p.default_model}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Model override" hint="Leave empty to use the provider's default model.">
        <Input name="model" placeholder="optional" />
      </Field>
      {ready.length > 0 && (
        <fieldset className="space-y-1">
          <legend className="text-sm font-medium text-slate-700">Limit to documents</legend>
          <p className="text-xs text-slate-500">None selected = all ready documents.</p>
          <div className="max-h-32 space-y-1 overflow-y-auto pt-1">
            {ready.map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-xs text-slate-700">
                <input type="checkbox" name="document_ids" value={d.id} className="rounded border-slate-300" />
                <span className="truncate">{d.filename}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <ErrorText error={create.error} />
      <Button type="submit" loading={create.isPending} className="w-full">
        Start conversation
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------- right: sources

function SourcesPanel({ citations, highlighted }: { citations: Citation[]; highlighted: number | null }) {
  const refs = useRef<Record<number, HTMLLIElement | null>>({});
  useEffect(() => {
    if (highlighted !== null) refs.current[highlighted]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [highlighted]);

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-slate-200 bg-white xl:flex">
      <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold">Sources</h2>
      {citations.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">Select an answer to see the passages it was based on.</p>
      ) : (
        <ul className="flex-1 space-y-3 overflow-y-auto p-4">
          {citations.map((c) => (
            <li
              key={c.citation_id}
              ref={(el) => {
                refs.current[c.citation_id] = el;
              }}
              className={cn(
                "rounded-lg p-3 text-sm ring-1 transition",
                highlighted === c.citation_id ? "bg-indigo-50 ring-indigo-300" : "ring-slate-200",
              )}
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded bg-indigo-100 text-xs font-semibold text-indigo-700">
                    {c.citation_id}
                  </span>
                  <span className="truncate font-medium" title={c.filename}>
                    {c.filename}
                  </span>
                </div>
                {c.score !== null && <span className="shrink-0 text-xs text-slate-400">{Math.round(c.score * 100)}%</span>}
              </div>
              <p className="line-clamp-6 text-xs leading-relaxed text-slate-600">{c.quoted_text}</p>
              <a
                href={fileUrl(c.document_id, c.page_number)}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-500"
              >
                <ExternalLink className="size-3" />
                {c.page_number ? `Open page ${c.page_number}` : "Open document"}
              </a>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------- center: chat

function AssistantMessage({
  message,
  selected,
  onSelect,
  onCite,
}: {
  message: ChatMessage;
  selected: boolean;
  onSelect: () => void;
  onCite: (n: number) => void;
}) {
  const valid = useMemo(() => new Set(message.citations.map((c) => c.citation_id)), [message.citations]);
  return (
    <div
      onClick={onSelect}
      className={cn("cursor-pointer rounded-lg bg-white p-4 ring-1 transition", selected ? "ring-indigo-300" : "ring-slate-200 hover:ring-slate-300")}
    >
      {message.status === "not_found" ? (
        <div className="flex items-start gap-2 text-sm text-slate-600">
          <SearchX className="mt-0.5 size-4 shrink-0 text-slate-400" />
          {message.content}
        </div>
      ) : (
        <AnswerMarkdown text={message.content} validCitations={valid} onCite={(n) => { onSelect(); onCite(n); }} />
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        {message.status === "completed" && !message.grounded && <Badge color="yellow">No citations</Badge>}
        {message.citations.length > 0 && <Badge color="blue">{message.citations.length} source{message.citations.length > 1 ? "s" : ""}</Badge>}
        {message.model && <span>{message.model}</span>}
        {message.latency_ms !== null && <span>· {(message.latency_ms / 1000).toFixed(1)}s</span>}
        {message.usage?.input_tokens != null && <span>· {message.usage.input_tokens + (message.usage.output_tokens ?? 0)} tokens</span>}
      </div>
    </div>
  );
}

function Chat({ conversation, onCitations }: { conversation: Conversation; onCitations: (c: Citation[], highlight: number | null) => void }) {
  const queryClient = useQueryClient();
  const { data: messages, isLoading } = useMessages(conversation.id);
  const [selected, setSelected] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: (question: string) =>
      api<Answer>(`conversations/${conversation.id}/messages`, { method: "POST", json: { question } }),
    onMutate: (question) => setPendingQuestion(question),
    onSuccess: async (answer) => {
      await queryClient.invalidateQueries({ queryKey: keys.messages(conversation.id) });
      // The first question becomes the conversation's title on the server.
      queryClient.invalidateQueries({ queryKey: ["workspaces"], predicate: (q) => q.queryKey[2] === "conversations" });
      setSelected(answer.message_id);
      onCitations(answer.citations, null);
      setDraft("");
    },
    onSettled: () => setPendingQuestion(null),
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages?.length, pendingQuestion]);

  function submit() {
    const question = draft.trim();
    if (question && !ask.isPending) ask.mutate(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  // Each assistant message shows which (rewritten) query was searched for the question before it.
  const lastAssistant = messages?.filter((m) => m.role === "assistant").at(-1);

  return (
    <section className="flex min-w-0 flex-1 flex-col">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h2 className="truncate font-medium">{conversation.title ?? "New conversation"}</h2>
        <p className="text-xs text-slate-500">
          {conversation.model}
          {conversation.document_ids.length > 0 && ` · limited to ${conversation.document_ids.length} document(s)`}
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {isLoading && <Spinner />}
        {!isLoading && !messages?.length && !pendingQuestion && (
          <EmptyState icon={<Sparkles className="size-5" />} title="Ask your documents anything">
            Answers only use your documents and cite the exact page. If the documents don&apos;t say, you&apos;ll be told so.
          </EmptyState>
        )}
        {messages?.map((m) =>
          m.role === "user" ? (
            <div key={m.message_id} className="ml-auto max-w-[80%] whitespace-pre-wrap rounded-lg bg-indigo-600 px-4 py-2.5 text-sm text-white">
              {m.content}
            </div>
          ) : (
            <div key={m.message_id} className="max-w-[90%] space-y-1">
              <AssistantMessage
                message={m}
                selected={selected === m.message_id}
                onSelect={() => {
                  setSelected(m.message_id);
                  onCitations(m.citations, null);
                }}
                onCite={(n) => onCitations(m.citations, n)}
              />
              {m.search_query && m === lastAssistant && (
                <p className="px-1 text-xs text-slate-400">Searched for: “{m.search_query}”</p>
              )}
            </div>
          ),
        )}
        {pendingQuestion && (
          <>
            <div className="ml-auto max-w-[80%] whitespace-pre-wrap rounded-lg bg-indigo-600/80 px-4 py-2.5 text-sm text-white">{pendingQuestion}</div>
            <Spinner label="Searching documents and writing an answer…" />
          </>
        )}
        <ErrorText error={ask.error} />
        <div ref={bottom} />
      </div>

      <div className="border-t border-slate-200 bg-white p-4">
        <div className="flex items-end gap-2 rounded-lg ring-1 ring-slate-300 focus-within:ring-2 focus-within:ring-indigo-600">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            maxLength={4000}
            placeholder="Ask a question about your documents…  (Enter to send, Shift+Enter for a new line)"
            className="flex-1 resize-none rounded-lg bg-transparent px-3 py-2 text-sm focus:outline-none"
          />
          <Button onClick={submit} loading={ask.isPending} disabled={!draft.trim()} className="m-1.5" aria-label="Send">
            <Send className="size-4" />
          </Button>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- page

export default function ResearchPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: conversations, isLoading } = useConversations(workspaceId);
  const [showNew, setShowNew] = useState(false);
  const [sources, setSources] = useState<{ citations: Citation[]; highlight: number | null }>({ citations: [], highlight: null });

  const activeId = searchParams.get("c") ?? conversations?.[0]?.id ?? null;
  const active = conversations?.find((c) => c.id === activeId) ?? null;

  const open = (id: string) => {
    setSources({ citations: [], highlight: null });
    router.replace(`/w/${workspaceId}/research?c=${id}`);
  };

  const remove = useMutation({
    mutationFn: (id: string) => api(`conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
      router.replace(`/w/${workspaceId}/research`);
    },
  });

  return (
    <div className="flex h-full">
      <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center justify-between px-4 py-3">
          <h2 className="text-sm font-semibold">Conversations</h2>
          <button onClick={() => setShowNew((v) => !v)} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" title="New conversation">
            <MessageSquarePlus className="size-4" />
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto px-3 pb-3">
          {(showNew || (!isLoading && !conversations?.length)) && (
            <NewConversation
              workspaceId={workspaceId}
              orgId={workspace?.organization_id}
              onCreated={(c) => {
                setShowNew(false);
                open(c.id);
              }}
            />
          )}
          <ul className="space-y-0.5">
            {conversations?.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  onClick={() => open(c.id)}
                  className={cn(
                    "w-full rounded-md px-2.5 py-2 pr-8 text-left",
                    c.id === activeId ? "bg-indigo-50 text-indigo-900" : "hover:bg-slate-50",
                  )}
                >
                  <p className="truncate text-sm">{c.title ?? "New conversation"}</p>
                  <p className="text-xs text-slate-400">{formatDate(c.created_at)}</p>
                </button>
                <button
                  onClick={() => confirm("Delete this conversation?") && remove.mutate(c.id)}
                  className="absolute top-2 right-1.5 hidden rounded p-1 text-slate-400 group-hover:block hover:bg-red-50 hover:text-red-600"
                  title="Delete conversation"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </div>
        <Link href={`/w/${workspaceId}/documents`} className="flex items-center gap-2 border-t border-slate-200 px-4 py-3 text-xs text-slate-500 hover:text-slate-700">
          <FileText className="size-3.5" /> Manage documents
        </Link>
      </aside>

      {active ? (
        <Chat key={active.id} conversation={active} onCitations={(citations, highlight) => setSources({ citations, highlight })} />
      ) : (
        <div className="flex flex-1 items-center justify-center">
          {isLoading ? <Spinner /> : <EmptyState icon={<MessageSquarePlus className="size-5" />} title="Start a conversation">Pick an AI provider on the left to begin.</EmptyState>}
        </div>
      )}
      <SourcesPanel citations={sources.citations} highlighted={sources.highlight} />
    </div>
  );
}
