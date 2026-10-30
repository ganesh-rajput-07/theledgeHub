"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, type FormEvent } from "react";

import { Button, Card, ErrorText, Field, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { keys, useOrganizations, useWorkspaces } from "@/lib/queries";
import type { Organization } from "@/types/api";

/** Sends the user to their first workspace, or asks them to create an organization. */
export default function HomePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: orgs, isLoading } = useOrganizations();
  const firstOrg = orgs?.[0];
  const { data: workspaces } = useWorkspaces(firstOrg?.id);

  useEffect(() => {
    if (!firstOrg || !workspaces) return;
    router.replace(workspaces[0] ? `/w/${workspaces[0].id}/research` : `/org/${firstOrg.id}/settings`);
  }, [firstOrg, workspaces, router]);

  const createOrg = useMutation({
    mutationFn: (name: string) => api<Organization>("organizations", { method: "POST", json: { name } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orgs }),
  });

  if (isLoading || firstOrg) return <Spinner label="Opening your workspace…" />;

  return (
    <div className="flex min-h-full items-center justify-center p-8">
      <Card className="w-full max-w-md p-6">
        <form
          className="space-y-4"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            createOrg.mutate(String(new FormData(e.currentTarget).get("name")));
          }}
        >
          <div className="flex items-center gap-3">
            <Building2 className="size-5 text-indigo-600" />
            <h1 className="font-semibold">Create your organization</h1>
          </div>
          <p className="text-sm text-slate-500">
            You aren&apos;t a member of any organization yet. Create one, or ask an admin to add you.
          </p>
          <Field label="Organization name">
            <Input name="name" required placeholder="Acme Inc." />
          </Field>
          <ErrorText error={createOrg.error} />
          <Button type="submit" loading={createOrg.isPending}>
            Create organization
          </Button>
        </form>
      </Card>
    </div>
  );
}
