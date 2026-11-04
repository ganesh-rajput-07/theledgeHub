"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Combine, FileOutput, RotateCw, Scissors } from "lucide-react";
import { useState } from "react";

import { Button, ErrorText, Field, Input, Modal, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import type { CreatedDocument, DocumentItem, DocumentOrigin } from "@/types/api";

/** Short human description of where a derived document came from. */
export function describeOrigin(origin: DocumentOrigin | null): string | null {
  if (!origin) return null;
  const from = origin.sources?.map((s) => s.filename) ?? [];
  switch (origin.operation) {
    case "photo":
      return `Photo · converted from ${origin.converted_from}`;
    case "merge":
      return `Merged from ${from.length} documents`;
    case "split":
      return `Split from ${from[0]} (page ${origin.pages})`;
    case "extract_pages":
      return `Pages ${origin.pages} of ${from[0]}`;
    case "rotate":
      return `Rotated copy of ${from[0]}`;
    default:
      return null;
  }
}

/** Ranges like "1-3,5" from a list of page numbers, keeping the user's order. */
function toSpec(pages: number[]): string {
  return pages.join(",");
}

// ---------------------------------------------------------------- merge

export function MergeDialog({
  workspaceId,
  documents,
  onClose,
  onDone,
}: {
  workspaceId: string;
  documents: DocumentItem[];
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [order, setOrder] = useState(documents);
  const [filename, setFilename] = useState("");

  const merge = useMutation({
    mutationFn: () =>
      api<CreatedDocument>(`workspaces/${workspaceId}/documents/merge`, {
        method: "POST",
        json: { document_ids: order.map((d) => d.id), filename: filename || null },
      }),
    onSuccess: (created) => onDone(`Created “${created.filename}”. It's being processed now.`),
  });

  function move(index: number, by: number) {
    const next = [...order];
    [next[index], next[index + by]] = [next[index + by], next[index]];
    setOrder(next);
  }

  return (
    <Modal
      title={`Merge ${order.length} documents`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={merge.isPending} onClick={() => merge.mutate()}>
            <Combine className="size-4" /> Merge into one PDF
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-500">Pages are combined in this order. The originals are kept unchanged.</p>
        <ol className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200">
          {order.map((doc, index) => (
            <li key={doc.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="w-5 text-right text-slate-400">{index + 1}.</span>
              <span className="min-w-0 flex-1 truncate">{doc.filename}</span>
              <span className="text-xs text-slate-400">{doc.page_count ?? "?"} p.</span>
              <button
                disabled={index === 0}
                onClick={() => move(index, -1)}
                className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30"
                aria-label={`Move ${doc.filename} up`}
              >
                <ArrowUp className="size-4" />
              </button>
              <button
                disabled={index === order.length - 1}
                onClick={() => move(index, 1)}
                className="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-30"
                aria-label={`Move ${doc.filename} down`}
              >
                <ArrowDown className="size-4" />
              </button>
            </li>
          ))}
        </ol>
        <Field label="Name of the new PDF" hint="Optional. Leave empty for an automatic name.">
          <Input
            value={filename}
            maxLength={200}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="Vendor invoices - October"
          />
        </Field>
        <ErrorText error={merge.error} />
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------- page tools

export function PageToolsDialog({
  document,
  onClose,
  onDone,
}: {
  document: DocumentItem;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const {
    data: info,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["documents", document.id, "pages"],
    queryFn: () => api<{ page_count: number }>(`documents/${document.id}/pages`),
  });
  const total = info?.page_count ?? 0;
  const pages = Array.from({ length: total }, (_, i) => i + 1);
  const toggle = (page: number) => setSelected((s) => (s.includes(page) ? s.filter((p) => p !== page) : [...s, page]));

  const action = useMutation({
    mutationFn: async (kind: "extract" | "split" | "rotate") => {
      if (kind === "extract") {
        const created = await api<CreatedDocument>(`documents/${document.id}/extract-pages`, {
          method: "POST",
          json: { pages: toSpec(selected) },
        });
        return `Created “${created.filename}” with ${selected.length} page(s).`;
      }
      if (kind === "split") {
        const parts = await api<CreatedDocument[]>(`documents/${document.id}/split`, { method: "POST", json: {} });
        return `Split into ${parts.length} documents, one per page. They're being processed now.`;
      }
      const created = await api<CreatedDocument>(`documents/${document.id}/rotate`, {
        method: "POST",
        json: { pages: selected.length ? toSpec(selected) : "1-", degrees: 90 },
      });
      return `Created “${created.filename}”.`;
    },
    onSuccess: onDone,
  });

  return (
    <Modal
      wide
      title={`Pages · ${document.filename}`}
      onClose={onClose}
      footer={
        <>
          <span className="mr-auto text-xs text-slate-500">
            {selected.length ? `${selected.length} page(s) selected, in click order` : "Click pages to select them"} ·
            originals are never changed
          </span>
          <Button variant="secondary" disabled={!total || action.isPending} onClick={() => action.mutate("rotate")}>
            <RotateCw className="size-4" /> Rotate {selected.length ? "selected" : "all"} 90°
          </Button>
          <Button variant="secondary" disabled={total < 2 || action.isPending} onClick={() => action.mutate("split")}>
            <Scissors className="size-4" /> One document per page
          </Button>
          <Button disabled={!selected.length} loading={action.isPending} onClick={() => action.mutate("extract")}>
            <FileOutput className="size-4" /> Keep selected pages
          </Button>
        </>
      }
    >
      {isLoading ? (
        <Spinner label="Reading pages…" />
      ) : (
        <div className="space-y-3">
          <ErrorText error={error ?? action.error} />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
            {pages.map((page) => {
              const position = selected.indexOf(page);
              return (
                <button
                  key={page}
                  onClick={() => toggle(page)}
                  aria-pressed={position >= 0}
                  aria-label={`Page ${page}`}
                  className={cn(
                    "relative rounded-md bg-slate-50 p-1.5 ring-2 transition",
                    position >= 0 ? "ring-indigo-500" : "ring-transparent hover:ring-slate-300",
                  )}
                >
                  {/* Plain <img>: the optimizer fetches server-side without the user's session cookie. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/backend/documents/${document.id}/pages/${page}/thumbnail?width=200`}
                    alt={`Page ${page}`}
                    loading="lazy"
                    className="mx-auto max-h-56 w-auto bg-white shadow-sm"
                  />
                  <span className="mt-1 block text-center text-xs text-slate-500">Page {page}</span>
                  {position >= 0 && (
                    <span className="absolute top-2 right-2 flex size-6 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                      {position + 1}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </Modal>
  );
}
