import { NextResponse } from "next/server";

import { BACKEND_URL, clearSessionCookies, isCrossSite, readSession } from "@/lib/server/session";

export async function POST(request: Request) {
  if (isCrossSite(request)) return NextResponse.json({ detail: "Cross-site request" }, { status: 403 });
  const { refreshToken } = await readSession();
  if (refreshToken) {
    // Revoke server-side too, so the refresh token is dead even if it was copied somewhere.
    await fetch(`${BACKEND_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    }).catch(() => undefined);
  }
  const result = NextResponse.json({ ok: true });
  clearSessionCookies(result);
  return result;
}
