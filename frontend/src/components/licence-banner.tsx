"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";

import { api, authRequest } from "@/lib/api";
import { DESKTOP, type LicenceStatus } from "@/lib/licence";

/** Installed app only: warns in the last hour of the licence session, so nobody is cut off mid-task. */
export function LicenceBanner() {
  const pathname = usePathname();
  const { data } = useQuery({
    queryKey: ["licence"],
    queryFn: () => api<LicenceStatus>("licence/status"),
    enabled: DESKTOP,
    refetchInterval: 60_000,
  });
  if (!DESKTOP || !data?.active || data.seconds_left === undefined || data.seconds_left > 3600) return null;

  const minutes = Math.max(1, Math.ceil(data.seconds_left / 60));

  async function signInAgain() {
    await authRequest("logout");
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `/login?next=${encodeURIComponent(pathname)}`;
  }

  return (
    <div className="flex items-center justify-between gap-4 border-b border-amber-200 bg-amber-50 px-6 py-2.5 text-sm text-amber-800">
      <span>
        Your licence session ends in <b>{minutes} minute{minutes === 1 ? "" : "s"}</b>. Save your work and sign in
        again to continue (internet needed for a few seconds).
      </span>
      <button
        onClick={signInAgain}
        className="shrink-0 rounded-md bg-amber-600 px-3 py-1.5 font-medium text-white hover:bg-amber-700"
      >
        Sign in again
      </button>
    </div>
  );
}
