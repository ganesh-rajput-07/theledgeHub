"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Download, Play, XCircle } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge, Button, Card, EmptyState, ErrorText, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";
import { cn } from "@/lib/format";
import {
  keys,
  useDocuments,
  useExtractionSchemas,
  useExtractions,
  useProviders,
  useWorkspace,
} from "@/lib/queries";
import type { Extraction, ExtractionSchema } from "@/types/api";

const statusBadge: Record<Extraction["status"], { color: "gray" | "yellow" | "green" | "red"; label: string }> = {
  processing: { color: "yellow", label: "Reading…" },
  needs_review: { color: "gray", label: "Needs review" },
  approved: { color: "green", label: "Approved" },
  failed: { color: "red", label: "Failed" },
};

function Editor({
  extraction,
  schema,
  onChanged,
}: {
  extraction: Extraction;
  schema: ExtractionSchema;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(schema.fields.map((f) => [f.key, String(extraction.values[f.key] ?? "")])),
  );
  const dirty = schema.fields.some((f) => draft[f.key] !== String(extraction.values[f.key] ?? ""));
  const base = `documents/${extraction.document_id}/extraction`;

  const save = useMutation({
    mutationFn: () => api(base, { method: "PATCH", json: { values: draft } }),
    onSuccess: onChanged,
  });
  const approve = useMutation({
    mutationFn: () => api(`${base}/approve`, { method: "POST" }),
    onSuccess: onChanged,
  });
  const errors = extraction.issues.filter((i) => i.severity === "error");
  const issuesFor = (key: string) => extraction.issues.filter((i) => i.field === key);

  return (
    <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
      <iframe
        title={extraction.filename}
        src={fileUrl(extraction.document_id)}
        className="h-full min-h-[32rem] w-full rounded-lg border border-slate-200 bg-white"
      />
      <div className="space-y-4 overflow-y-auto">
        {extraction.error_message && (
          <p className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {extraction.error_message}
          </p>
        )}
        <Card className="space-y-3 p-4">
          {schema.fields.map((field) => {
            const problems = issuesFor(field.key);
            const worst = problems.some((p) => p.severity === "error") ? "error" : problems.length ? "warning" : null;
            return (
              <label key={field.key} className="block space-y-1">
                <span className="text-xs font-medium text-slate-600">
                  {field.label}
                  {field.required && <span className="text-red-500"> *</span>}
                </span>
                <Input
                  value={draft[field.key]}
                  inputMode={field.type === "amount" ? "decimal" : undefined}
                  onChange={(e) => setDraft({ ...draft, [field.key]: e.target.value })}
                  className={cn(worst === "error" && "ring-red-400", worst === "warning" && "ring-amber-400")}
                />
                {problems.map((p) => (
                  <span key={p.code} className={cn("block text-xs", p.severity === "error" ? "text-red-600" : "text-amber-600")}>
                    {p.message}
                  </span>
                ))}
              </label>
            );
          })}
        </Card>
        {extraction.issues
          .filter((i) => i.field === null)
          .map((i) => (
            <p key={i.code} className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
              <XCircle className="mt-0.5 size-4 shrink-0" />
              {i.message}
            </p>
          ))}
        <ErrorText error={save.error ?? approve.error} />
        <div className="flex items-center gap-2">
          <Button variant="secondary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>
            Save changes
          </Button>
          <Button
            disabled={dirty || errors.length > 0 || extraction.status === "approved"}
            loading={approve.isPending}
            onClick={() => approve.mutate()}
            title={dirty ? "Save your changes first" : errors.length ? "Fix the problems first" : undefined}
          >
            <CheckCircle2 className="size-4" />
            {extraction.status === "approved" ? "Approved" : "Approve"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: providers } = useProviders(workspace?.organization_id);
  const { data: schemas } = useExtractionSchemas();
  const { data: documents } = useDocuments(workspaceId);
  const { data: extractions, isLoading, error } = useExtractions(workspaceId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [providerId, setProviderId] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.extractions(workspaceId) });

  const schema = schemas?.find((s) => s.key === "invoice");
  const provider = providers?.find((p) => p.id === providerId);
  const extracted = new Set(extractions?.map((e) => e.document_id));
  const pending = documents?.filter((d) => !extracted.has(d.id)) ?? [];
  const selected = extractions?.find((e) => e.document_id === selectedId) ?? extractions?.[0];

  const run = useMutation({
    mutationFn: async (ids: string[]) => {
      const failures: string[] = [];
      for (const id of ids) {
        try {
          await api(`documents/${id}/extraction`, {
            method: "POST",
            json: provider ? { provider_id: provider.id, model: provider.default_model } : {},
          });
        } catch (err) {
          failures.push((err as Error).message);
        }
        await refresh();
      }
      if (failures.length) throw new Error(failures.join("\n"));
    },
  });

  return (
    <>
      <PageHeader
        title="Review"
        description="Check extracted data against the original, fix anything wrong, then approve."
        actions={
          <div className="flex items-center gap-2">
            <Select value={providerId} onChange={(e) => setProviderId(e.target.value)} aria-label="Reader">
              <option value="">Rules only (fastest)</option>
              {providers?.filter((p) => p.is_active).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} · {p.default_model}
                </option>
              ))}
            </Select>
            <Button loading={run.isPending} disabled={!pending.length} onClick={() => run.mutate(pending.map((d) => d.id))}>
              <Play className="size-4" />
              Extract {pending.length || ""} new
            </Button>
            <a
              href={`/api/backend/workspaces/${workspaceId}/extractions/export`}
              className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
            >
              <Download className="size-4" />
              Excel
            </a>
          </div>
        }
      />
      <div className="flex h-[calc(100vh-5.5rem)] flex-col gap-4 p-8">
        <ErrorText error={error ?? run.error} />
        {isLoading || !schema ? (
          <Spinner />
        ) : !extractions?.length ? (
          <Card>
            <EmptyState icon={<ClipboardCheck className="size-5" />} title="Nothing to review yet">
              Upload invoices in Documents, then choose “Extract new” to read their fields.
            </EmptyState>
          </Card>
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-[18rem_1fr] gap-4">
            <Card className="overflow-y-auto">
              <ul className="divide-y divide-slate-100">
                {extractions.map((e) => (
                  <li key={e.id}>
                    <button
                      onClick={() => setSelectedId(e.document_id)}
                      className={cn(
                        "w-full px-4 py-3 text-left hover:bg-slate-50",
                        selected?.id === e.id && "bg-indigo-50 hover:bg-indigo-50",
                      )}
                    >
                      <p className="truncate text-sm font-medium">{e.filename}</p>
                      <div className="mt-1 flex items-center gap-2">
                        <Badge color={statusBadge[e.status].color}>{statusBadge[e.status].label}</Badge>
                        {e.status === "needs_review" && e.issues.length > 0 && (
                          <span className="text-xs text-amber-600">
                            {e.issues.length} issue{e.issues.length > 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
            {selected && selected.status === "failed" ? (
              <Card className="space-y-3 p-6">
                <p className="text-sm text-red-600">{selected.error_message ?? "Extraction failed"}</p>
                <Button variant="secondary" loading={run.isPending} onClick={() => run.mutate([selected.document_id])}>
                  Try again
                </Button>
              </Card>
            ) : selected && selected.status === "processing" ? (
              <Spinner label="Reading the document…" />
            ) : (
              selected && (
                <Editor
                  key={`${selected.id}:${selected.updated_at}`}
                  extraction={selected}
                  schema={schema}
                  onChanged={refresh}
                />
              )
            )}
          </div>
        )}
      </div>
    </>
  );
}
