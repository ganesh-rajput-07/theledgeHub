import { redirect } from "next/navigation";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Spinner } from "@/components/ui";
import { readSession } from "@/lib/server/session";

// Reads the session cookie at request time, so it must sit inside <Suspense> (Cache Components).
async function RequireSession({ children }: { children: React.ReactNode }) {
  const { refreshToken } = await readSession();
  if (!refreshToken) redirect("/login");
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<Spinner />}>
      <RequireSession>{children}</RequireSession>
    </Suspense>
  );
}
