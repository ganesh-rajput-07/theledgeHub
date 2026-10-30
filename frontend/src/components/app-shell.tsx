"use client";

import { BookOpenText, FileText, LayoutDashboard, LogOut, MessageSquareText, Settings } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { authRequest, api } from "@/lib/api";
import { cn } from "@/lib/format";
import { useMe, useOrganizations, useWorkspace, useWorkspaces } from "@/lib/queries";
import type { Workspace } from "@/types/api";

function NavLink({ href, icon, children }: { href: string; icon: ReactNode; children: ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm",
        active ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-600 hover:bg-slate-100",
      )}
    >
      {icon}
      {children}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const params = useParams<{ workspaceId?: string; orgId?: string }>();
  const { data: me } = useMe();
  const { data: orgs } = useOrganizations();
  const { data: workspace } = useWorkspace(params.workspaceId);

  const orgId = params.orgId ?? workspace?.organization_id ?? orgs?.[0]?.id;
  const org = orgs?.find((o) => o.id === orgId);
  const { data: workspaces } = useWorkspaces(orgId);
  const wsId = params.workspaceId;

  async function switchOrg(id: string) {
    const list = await api<Workspace[]>(`organizations/${id}/workspaces`);
    router.push(list[0] ? `/w/${list[0].id}/research` : `/org/${id}/settings`);
  }

  async function logout() {
    await authRequest("logout");
    // Full reload on purpose: it wipes the in-memory query cache holding this user's data.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }

  return (
    <div className="flex h-full">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="rounded-lg bg-indigo-600 p-1.5 text-white">
            <BookOpenText className="size-4" aria-hidden />
          </div>
          <span className="font-semibold">KnowledgeHub AI</span>
        </div>

        {orgs && orgs.length > 0 && (
          <div className="px-3">
            <label className="sr-only" htmlFor="org-switcher">
              Organization
            </label>
            <select
              id="org-switcher"
              value={orgId}
              onChange={(e) => switchOrg(e.target.value)}
              className="w-full rounded-md border-0 bg-slate-50 px-2.5 py-1.5 text-sm font-medium ring-1 ring-slate-200 focus:ring-2 focus:ring-indigo-600 focus:outline-none"
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
          <div>
            <p className="px-2.5 pb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Workspaces</p>
            <div className="space-y-0.5">
              {workspaces?.map((w) => (
                <Link
                  key={w.id}
                  href={`/w/${w.id}/research`}
                  className={cn(
                    "block truncate rounded-md px-2.5 py-1.5 text-sm",
                    w.id === wsId ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-50",
                  )}
                >
                  {w.name}
                </Link>
              ))}
            </div>
          </div>

          {wsId && (
            <div>
              <p className="truncate px-2.5 pb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                {workspace?.name ?? "Workspace"}
              </p>
              <div className="space-y-0.5">
                <NavLink href={`/w/${wsId}`} icon={<LayoutDashboard className="size-4" />}>
                  Overview
                </NavLink>
                <NavLink href={`/w/${wsId}/documents`} icon={<FileText className="size-4" />}>
                  Documents
                </NavLink>
                <NavLink href={`/w/${wsId}/research`} icon={<MessageSquareText className="size-4" />}>
                  Research
                </NavLink>
              </div>
            </div>
          )}
        </nav>

        <div className="space-y-1 border-t border-slate-200 p-3">
          {orgId && (
            <NavLink href={`/org/${orgId}/settings`} icon={<Settings className="size-4" />}>
              {org?.name ?? "Organization"} settings
            </NavLink>
          )}
          <div className="flex items-center justify-between gap-2 px-2.5 py-1.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{me?.full_name || me?.email}</p>
              <p className="truncate text-xs text-slate-500">{org ? `${org.role} · ${me?.email}` : me?.email}</p>
            </div>
            <button onClick={logout} title="Sign out" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100">
              <LogOut className="size-4" />
              <span className="sr-only">Sign out</span>
            </button>
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
