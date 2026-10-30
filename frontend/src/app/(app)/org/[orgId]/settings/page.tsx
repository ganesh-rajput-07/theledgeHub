"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FolderPlus, History, KeyRound, Trash2, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Badge, Button, Card, ErrorText, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { keys, useAuditLog, useMe, useMembers, useOrganizations, useProviders, useWorkspaces } from "@/lib/queries";
import type { ProviderName, Role } from "@/types/api";

const PROVIDERS: { value: ProviderName; label: string; needsKey: boolean; models: string[] }[] = [
  { value: "anthropic", label: "Anthropic (Claude)", needsKey: true, models: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"] },
  { value: "openai", label: "OpenAI", needsKey: true, models: [] },
  { value: "gemini", label: "Google Gemini", needsKey: true, models: [] },
  { value: "ollama", label: "Ollama (local, free)", needsKey: false, models: [] },
  { value: "mock", label: "Mock (offline testing)", needsKey: false, models: ["mock-1"] },
];

function Section({ icon, title, description, children }: { icon: ReactNode; title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <div className="flex items-start gap-3 border-b border-slate-200 px-6 py-4">
        <div className="mt-0.5 text-indigo-600">{icon}</div>
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
      </div>
      <div className="space-y-4 p-6">{children}</div>
    </Card>
  );
}

// ---------------------------------------------------------------- providers

function Providers({ orgId, canManage }: { orgId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const { data: providers, isLoading } = useProviders(orgId);
  const [kind, setKind] = useState<ProviderName>("anthropic");
  const [models, setModels] = useState<Record<string, string[]>>({});
  const meta = PROVIDERS.find((p) => p.value === kind)!;
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.providers(orgId) });

  const add = useMutation({
    mutationFn: (payload: Record<string, string | null>) =>
      api(`organizations/${orgId}/providers`, { method: "POST", json: payload }),
    onSuccess: refresh,
  });
  const validate = useMutation({
    mutationFn: (id: string) => api<{ provider_id: string; models: string[] }>(`providers/${id}/validate`, { method: "POST" }),
    onSuccess: (result) => {
      setModels((m) => ({ ...m, [result.provider_id]: result.models }));
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`providers/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    add.mutate(
      {
        provider: kind,
        label: String(data.get("label")),
        default_model: String(data.get("default_model")),
        api_key: meta.needsKey ? String(data.get("api_key")) : null,
        base_url: kind === "ollama" ? String(data.get("base_url") || "") || null : null,
      },
      { onSuccess: () => form.reset() }, // never keep the key around in the form
    );
  }

  return (
    <Section
      icon={<KeyRound className="size-5" />}
      title="AI providers"
      description="Bring your own key. Keys are checked with the provider, stored encrypted, and never shown again."
    >
      {isLoading ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200">
          {providers?.map((p) => (
            <li key={p.id} className="space-y-2 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {p.label} <span className="font-normal text-slate-500">· {p.provider}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    Default model <code className="font-mono">{p.default_model}</code>
                    {p.key_hint && <> · key {p.key_hint}</>}
                    {p.base_url && <> · {p.base_url}</>}
                    {p.last_validated_at && <> · checked {formatDate(p.last_validated_at)}</>}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!p.is_active && <Badge color="gray">Disabled</Badge>}
                  <Button variant="secondary" onClick={() => validate.mutate(p.id)} loading={validate.isPending && validate.variables === p.id}>
                    <CheckCircle2 className="size-4" /> Test
                  </Button>
                  {canManage && (
                    <Button variant="danger" onClick={() => confirm(`Delete “${p.label}”? Its key is erased.`) && remove.mutate(p.id)}>
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
              </div>
              {models[p.id] && (
                <p className="text-xs text-emerald-700">
                  ✓ Key works · {models[p.id].length} models available: {models[p.id].slice(0, 8).join(", ")}
                  {models[p.id].length > 8 && " …"}
                </p>
              )}
            </li>
          ))}
          {!providers?.length && <li className="px-4 py-6 text-sm text-slate-500">No providers connected yet.</li>}
        </ul>
      )}
      <ErrorText error={validate.error ?? remove.error} />

      {canManage ? (
        <form onSubmit={onSubmit} className="grid gap-4 rounded-md bg-slate-50 p-4 ring-1 ring-slate-200 sm:grid-cols-2">
          <Field label="Provider">
            <Select value={kind} onChange={(e) => setKind(e.target.value as ProviderName)}>
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Label">
            <Input name="label" required placeholder="e.g. Team Claude key" />
          </Field>
          {meta.needsKey && (
            <Field label="API key" hint="Sent once over a secure channel, then stored encrypted.">
              <Input name="api_key" type="password" required autoComplete="off" spellCheck={false} />
            </Field>
          )}
          {kind === "ollama" && (
            <Field label="Ollama URL" hint="As reachable from the backend server.">
              <Input name="base_url" placeholder="http://localhost:11434" />
            </Field>
          )}
          <Field label="Default model" hint={meta.models.length ? undefined : "Exact model name, e.g. from your provider's console or `ollama list`."}>
            <Input name="default_model" required list={`models-${kind}`} defaultValue={meta.models[0] ?? ""} key={kind} />
            <datalist id={`models-${kind}`}>
              {meta.models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </Field>
          <div className="flex items-end sm:col-span-2">
            <Button type="submit" loading={add.isPending}>
              Connect provider
            </Button>
          </div>
          <div className="sm:col-span-2">
            <ErrorText error={add.error} />
          </div>
        </form>
      ) : (
        <p className="text-sm text-slate-500">Only owners and admins can add or remove provider keys.</p>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- members

function Members({ orgId, myRole, myId }: { orgId: string; myRole: Role; myId?: string }) {
  const queryClient = useQueryClient();
  const { data: members, isLoading } = useMembers(orgId);
  const canManage = myRole !== "member";
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.members(orgId) });

  const add = useMutation({
    mutationFn: (payload: { email: string; role: Role }) => api(`organizations/${orgId}/members`, { method: "POST", json: payload }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (userId: string) => api(`organizations/${orgId}/members/${userId}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  return (
    <Section icon={<Users className="size-5" />} title="Members" description="Members can upload, search and chat. Owners and admins also manage keys, members and workspaces.">
      {isLoading ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200">
          {members?.map((m) => (
            <li key={m.user_id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {m.full_name || m.email} {m.user_id === myId && <span className="font-normal text-slate-400">(you)</span>}
                </p>
                <p className="truncate text-xs text-slate-500">{m.email}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge color={m.role === "owner" ? "blue" : "gray"}>{m.role}</Badge>
                {canManage && m.user_id !== myId && (
                  <button onClick={() => confirm(`Remove ${m.email}?`) && remove.mutate(m.user_id)} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" title="Remove member">
                    <Trash2 className="size-4" />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={remove.error} />
      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            add.mutate({ email: String(data.get("email")), role: data.get("role") as Role }, { onSuccess: () => form.reset() });
          }}
        >
          <div className="min-w-56 flex-1">
            <Field label="Add member by email" hint="They need to register first.">
              <Input name="email" type="email" required placeholder="colleague@company.com" />
            </Field>
          </div>
          <Field label="Role">
            <Select name="role" defaultValue="member">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              {myRole === "owner" && <option value="owner">Owner</option>}
            </Select>
          </Field>
          <Button type="submit" loading={add.isPending} className="mb-[1.375rem]">
            <UserPlus className="size-4" /> Add
          </Button>
          <div className="w-full">
            <ErrorText error={add.error} />
          </div>
        </form>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- workspaces

function Workspaces({ orgId, canManage }: { orgId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const { data: workspaces } = useWorkspaces(orgId);
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.workspaces(orgId) });

  const create = useMutation({
    mutationFn: (payload: { name: string; description: string | null }) =>
      api(`organizations/${orgId}/workspaces`, { method: "POST", json: payload }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`workspaces/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  return (
    <Section icon={<FolderPlus className="size-5" />} title="Workspaces" description="Separate knowledge collections, e.g. HR, Finance, Product docs. Search never crosses workspaces.">
      <ul className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200">
        {workspaces?.map((w) => (
          <li key={w.id} className="flex items-center justify-between px-4 py-3 text-sm">
            <Link href={`/w/${w.id}/research`} className="font-medium hover:text-indigo-600">
              {w.name}
              {w.description && <span className="ml-2 font-normal text-slate-500">{w.description}</span>}
            </Link>
            {canManage && (
              <button
                onClick={() => confirm(`Delete workspace “${w.name}”? All its documents and conversations are permanently deleted.`) && remove.mutate(w.id)}
                className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                title="Delete workspace"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      <ErrorText error={remove.error ?? create.error} />
      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            create.mutate(
              { name: String(data.get("name")), description: String(data.get("description") || "") || null },
              { onSuccess: () => form.reset() },
            );
          }}
        >
          <div className="min-w-48 flex-1">
            <Field label="New workspace">
              <Input name="name" required placeholder="Finance" />
            </Field>
          </div>
          <div className="min-w-48 flex-1">
            <Field label="Description">
              <Input name="description" placeholder="optional" />
            </Field>
          </div>
          <Button type="submit" loading={create.isPending}>
            Create
          </Button>
        </form>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- activity (audit trail)

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "Signed in",
  "organization.create": "Created the organization",
  "document.upload": "Uploaded",
  "document.delete": "Deleted document",
  "provider.create": "Connected provider",
  "provider.update": "Changed provider",
  "provider.delete": "Removed provider",
  "member.add": "Added a member",
  "member.remove": "Removed a member",
  "workspace.create": "Created workspace",
  "workspace.delete": "Deleted workspace",
};

function Activity({ orgId }: { orgId: string }) {
  const { data: entries, isLoading, error } = useAuditLog(orgId, true);
  return (
    <Section icon={<History className="size-5" />} title="Activity" description="Security-relevant actions in this organization (last 50). Visible to owners and admins.">
      {isLoading ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-md text-sm ring-1 ring-slate-200">
          {entries?.map((e) => {
            const name = (e.details.filename ?? e.details.label ?? e.details.name) as string | undefined;
            return (
              <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-2.5">
                <span>
                  <span className="font-medium">{e.actor_email ?? "Someone"}</span>{" "}
                  <span className="text-slate-600">{(ACTION_LABELS[e.action] ?? e.action).toLowerCase()}</span>
                  {name && <span className="text-slate-900"> “{name}”</span>}
                  {e.action === "provider.update" && e.details.key_rotated === true && <span className="text-slate-600"> (key rotated)</span>}
                </span>
                <span className="text-xs text-slate-400">
                  {formatDate(e.created_at)}
                  {e.ip_address && ` · ${e.ip_address}`}
                </span>
              </li>
            );
          })}
          {!entries?.length && <li className="px-4 py-6 text-slate-500">No activity yet.</li>}
        </ul>
      )}
      <ErrorText error={error} />
    </Section>
  );
}

export default function SettingsPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { data: orgs, isLoading } = useOrganizations();
  const { data: me } = useMe();
  const org = orgs?.find((o) => o.id === orgId);

  if (isLoading) return <Spinner />;
  if (!org) return <p className="p-8 text-sm text-slate-500">Organization not found.</p>;
  const canManage = org.role !== "member";

  return (
    <>
      <PageHeader title={`${org.name} settings`} description={`You are ${/^[aeiou]/.test(org.role) ? "an" : "a"} ${org.role} of this organization.`} />
      <div className="max-w-4xl space-y-6 p-8">
        <Providers orgId={orgId} canManage={canManage} />
        <Members orgId={orgId} myRole={org.role} myId={me?.id} />
        <Workspaces orgId={orgId} canManage={canManage} />
        {canManage && <Activity orgId={orgId} />}
      </div>
    </>
  );
}
