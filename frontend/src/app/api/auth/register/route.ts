import { NextResponse } from "next/server";

import { BACKEND_URL, forwardedFor, isCrossSite, setSessionCookies, type TokenPair } from "@/lib/server/session";

export async function POST(request: Request) {
  if (isCrossSite(request)) return NextResponse.json({ detail: "Cross-site request" }, { status: 403 });
  const body = await request.json();
  const registered = await fetch(`${BACKEND_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...forwardedFor(request) },
    body: JSON.stringify({
      email: body.email,
      password: body.password,
      full_name: body.full_name || null,
      organization_name: body.organization_name || null,
    }),
    cache: "no-store",
  });
  if (!registered.ok) return NextResponse.json(await registered.json(), { status: registered.status });

  // Sign the new user straight in.
  const login = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...forwardedFor(request) },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: "no-store",
  });
  if (!login.ok) return NextResponse.json(await login.json(), { status: login.status });

  const result = NextResponse.json({ ok: true }, { status: 201 });
  setSessionCookies(result, (await login.json()) as TokenPair);
  return result;
}
