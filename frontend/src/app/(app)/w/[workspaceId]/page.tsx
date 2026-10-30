"use client";

import { AlertTriangle, FileText, KeyRound, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";

import { Card, PageHeader, Spinner } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { useConversations, useDocuments, useProviders, useWorkspace } from "@/lib/queries";

function Stat({ label, value, icon, href }: { label: string; value: ReactNode; icon: ReactNode; href: string }) {
  return (
    <Link href={href}>
      <Card className="flex items-center gap-4 p-5 transition hover:ring-indigo-300">
        <div className="rounded-lg bg-indigo-50 p-2.5 text-indigo-600">{icon}</div>
        <div>
          <p className="text-2xl font-semibold">{value}</p>
          <p className="text-sm text-slate-500">{label}</p>
        </div>
      </Card>
    </Link>
  );
}

export default function OverviewPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: documents, isLoading } = useDocuments(workspaceId);
  const { data: conversations } = useConversations(workspaceId);
  const { data: providers } = useProviders(workspace?.organization_id);

  if (isLoading) return <Spinner />;
  const ready = documents?.filter((d) => d.status === "completed").length ?? 0;
  const failed = documents?.filter((d) => d.status === "failed").length ?? 0;
  const activeProviders = providers?.filter((p) => p.is_active).length ?? 0;

  return (
    <>
      <PageHeader title={workspace?.name ?? "Workspace"} description={workspace?.description ?? "Workspace overview"} />
      <div className="space-y-6 p-8">
        <div className="grid gap-4 sm:grid-cols-3">
          <Stat label="Documents ready" value={`${ready} / ${documents?.length ?? 0}`} icon={<FileText className="size-5" />} href={`/w/${workspaceId}/documents`} />
          <Stat label="Your conversations" value={conversations?.length ?? 0} icon={<MessageSquareText className="size-5" />} href={`/w/${workspaceId}/research`} />
          <Stat label="AI providers" value={activeProviders} icon={<KeyRound className="size-5" />} href={`/org/${workspace?.organization_id}/settings`} />
        </div>

        {failed > 0 && (
          <Card className="flex items-center gap-3 p-4 text-sm text-amber-800 ring-amber-200">
            <AlertTriangle className="size-4" />
            {failed} document{failed > 1 ? "s" : ""} failed to process.{" "}
            <Link href={`/w/${workspaceId}/documents`} className="font-medium underline">
              Review
            </Link>
          </Card>
        )}
        {activeProviders === 0 && (
          <Card className="flex items-center gap-3 p-4 text-sm text-slate-600">
            <KeyRound className="size-4 text-indigo-600" />
            Connect an AI provider (your own API key, or local Ollama) before asking questions.{" "}
            <Link href={`/org/${workspace?.organization_id}/settings`} className="font-medium text-indigo-600">
              Open settings
            </Link>
          </Card>
        )}

        <Card>
          <h2 className="border-b border-slate-200 px-5 py-3 text-sm font-semibold">Recent documents</h2>
          <ul className="divide-y divide-slate-100">
            {documents?.slice(0, 5).map((d) => (
              <li key={d.id} className="flex items-center justify-between px-5 py-3 text-sm">
                <span className="truncate">{d.filename}</span>
                <span className="shrink-0 text-slate-500">{formatDate(d.created_at)}</span>
              </li>
            ))}
            {!documents?.length && <li className="px-5 py-6 text-sm text-slate-500">No documents yet.</li>}
          </ul>
        </Card>
      </div>
    </>
  );
}
