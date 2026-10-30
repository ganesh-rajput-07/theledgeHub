import { NextResponse } from "next/server";

import { BACKEND_URL, isCrossSite, setSessionCookies, type TokenPair } from "@/lib/server/session";

export async function POST(request: Request) {
  if (isCrossSite(request)) return NextResponse.json({ detail: "Cross-site request" }, { status: 403 });
  const body = await request.json();
  const response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok) return NextResponse.json(data, { status: response.status });

  const result = NextResponse.json({ ok: true });
  setSessionCookies(result, data as TokenPair);
  return result;
}
