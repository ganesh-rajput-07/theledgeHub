"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, RotateCw, ScanText, Trash2, Upload } from "lucide-react";
import { useParams } from "next/navigation";
import { useRef, useState, type DragEvent } from "react";

import { Badge, Button, Card, EmptyState, ErrorText, PageHeader, Spinner } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";
import { cn, formatBytes, formatDate } from "@/lib/format";
import { keys, useDocuments } from "@/lib/queries";
import type { DocumentItem, DocumentStatusInfo } from "@/types/api";

const ACCEPT = ".pdf,.docx,.txt,.md";

const statusBadge: Record<DocumentItem["status"], { color: "gray" | "yellow" | "green" | "red"; label: string }> = {
  pending: { color: "gray", label: "Queued" },
  processing: { color: "yellow", label: "Processing" },
  completed: { color: "green", label: "Ready" },
  failed: { color: "red", label: "Failed" },
};

function FailureReason({ documentId }: { documentId: string }) {
  const [reason, setReason] = useState<string | null>(null);
  return reason ? (
    <p className="mt-1 text-xs text-red-600">{reason}</p>
  ) : (
    <button
      className="mt-1 text-xs text-red-600 underline"
      onClick={async () =>
        setReason((await api<DocumentStatusInfo>(`documents/${documentId}/status`)).error_message ?? "Unknown error")
      }
    >
      Why?
    </button>
  );
}

export default function DocumentsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const { data: documents, isLoading, error } = useDocuments(workspaceId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.documents(workspaceId) });

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const failures: string[] = [];
      for (const file of files) {
        const body = new FormData();
        body.append("file", file);
        try {
          await api(`workspaces/${workspaceId}/documents`, { method: "POST", body });
        } catch (err) {
          failures.push(`${file.name}: ${(err as Error).message}`);
        }
        await refresh();
      }
      if (failures.length) throw new Error(failures.join("\n"));
    },
  });

  const reprocess = useMutation({
    mutationFn: (id: string) => api(`documents/${id}/reprocess`, { method: "POST" }),
    onSettled: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`documents/${id}`, { method: "DELETE" }),
    onSettled: refresh,
  });

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) upload.mutate(Array.from(event.dataTransfer.files));
  }

  return (
    <>
      <PageHeader
        title="Documents"
        description="PDF, DOCX, TXT and Markdown. Scanned PDFs are read with OCR."
        actions={
          <Button onClick={() => inputRef.current?.click()} loading={upload.isPending}>
            <Upload className="size-4" />
            Upload
          </Button>
        }
      />
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files?.length) upload.mutate(Array.from(e.target.files));
          e.target.value = "";
        }}
      />
      <div className="space-y-4 p-8">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "rounded-lg border-2 border-dashed px-6 py-8 text-center text-sm transition-colors",
            dragging ? "border-indigo-400 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-500",
          )}
        >
          Drag files here, or{" "}
          <button className="font-medium text-indigo-600" onClick={() => inputRef.current?.click()}>
            browse
          </button>
          . Max 25 MB each.
        </div>
        {upload.error && <pre className="whitespace-pre-wrap"><ErrorText error={upload.error} /></pre>}
        <ErrorText error={error ?? reprocess.error ?? remove.error} />

        <Card className="overflow-hidden">
          {isLoading ? (
            <Spinner />
          ) : !documents?.length ? (
            <EmptyState icon={<FileText className="size-5" />} title="No documents yet">
              Upload reports, policies or manuals. Once a document is ready you can ask questions about it in Research.
            </EmptyState>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Pages</th>
                  <th className="px-5 py-3 font-medium">Size</th>
                  <th className="px-5 py-3 font-medium">Uploaded</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr key={doc.id} className="align-top">
                    <td className="max-w-xs px-5 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 shrink-0 text-slate-400" />
                        <span className="truncate font-medium">{doc.filename}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <Badge color={statusBadge[doc.status].color}>{statusBadge[doc.status].label}</Badge>
                      {doc.status === "failed" && <FailureReason documentId={doc.id} />}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{doc.page_count ?? "—"}</td>
                    <td className="px-5 py-3 text-slate-600">{formatBytes(doc.file_size)}</td>
                    <td className="px-5 py-3 text-slate-600">{formatDate(doc.created_at)}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <a href={fileUrl(doc.id)} target="_blank" rel="noreferrer" title="Open file" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100">
                          <ExternalLink className="size-4" />
                        </a>
                        <button
                          title="Process again"
                          disabled={doc.status === "processing"}
                          onClick={() => reprocess.mutate(doc.id)}
                          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40"
                        >
                          <RotateCw className="size-4" />
                        </button>
                        <button
                          title="Delete"
                          onClick={() => confirm(`Delete “${doc.filename}” and its indexed data?`) && remove.mutate(doc.id)}
                          className="rounded-md p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <p className="flex items-center gap-1.5 text-xs text-slate-400">
          <ScanText className="size-3.5" /> Text is extracted page by page so every answer can cite its exact page.
        </p>
      </div>
    </>
  );
}
