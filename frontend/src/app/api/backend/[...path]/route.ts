import { NextRequest, NextResponse } from "next/server";

import {
  BACKEND_URL,
  clearSessionCookies,
  getAccessToken,
  isCrossSite,
  setSessionCookies,
} from "@/lib/server/session";

// Response headers worth passing back to the browser (file downloads need the last three).
const PASS_HEADERS = ["content-type", "content-disposition", "cache-control", "x-content-type-options"];

async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  if (isCrossSite(request)) return NextResponse.json({ detail: "Cross-site request" }, { status: 403 });

  const { path } = await ctx.params;
  const { token, refreshed } = await getAccessToken();
  if (!token) {
    const response = NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    clearSessionCookies(response);
    return response;
  }

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const upstream = await fetch(`${BACKEND_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    // Streamed straight through, so large uploads are never buffered in memory here.
    body: hasBody ? request.body : undefined,
    // @ts-expect-error - required by Node's fetch when streaming a request body
    duplex: hasBody ? "half" : undefined,
    cache: "no-store",
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  for (const name of PASS_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  const body = upstream.status === 204 ? null : upstream.body;
  const response = new NextResponse(body, { status: upstream.status, headers: responseHeaders });
  if (refreshed) setSessionCookies(response, refreshed);
  if (upstream.status === 401) clearSessionCookies(response);
  return response;
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST };
