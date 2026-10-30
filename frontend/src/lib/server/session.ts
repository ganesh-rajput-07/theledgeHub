import "server-only";

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";

const ACCESS_COOKIE = "kh_access";
const REFRESH_COOKIE = "kh_refresh";
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7; // matches REFRESH_TOKEN_EXPIRE_DAYS on the backend

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

// Tokens live only in httpOnly cookies: page JavaScript can never read them, so an XSS bug
// cannot steal a session the way it could from localStorage.
const cookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  // Secure by default in production. Set COOKIE_SECURE=false only for plain-HTTP setups on a LAN address
  // (browsers already treat http://localhost as secure).
  secure: process.env.COOKIE_SECURE ? process.env.COOKIE_SECURE === "true" : process.env.NODE_ENV === "production",
  path: "/",
};

export function setSessionCookies(response: NextResponse, tokens: TokenPair) {
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, { ...cookieOptions, maxAge: tokens.expires_in });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, { ...cookieOptions, maxAge: REFRESH_MAX_AGE });
}

export function clearSessionCookies(response: NextResponse) {
  response.cookies.set(ACCESS_COOKIE, "", { ...cookieOptions, maxAge: 0 });
  response.cookies.set(REFRESH_COOKIE, "", { ...cookieOptions, maxAge: 0 });
}

export async function readSession() {
  const store = await cookies();
  return {
    accessToken: store.get(ACCESS_COOKIE)?.value,
    refreshToken: store.get(REFRESH_COOKIE)?.value,
  };
}

/** Seconds until a JWT expires (no signature check: the backend verifies; this only decides when to refresh). */
function secondsLeft(token: string | undefined): number {
  if (!token) return 0;
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());
    return payload.exp - Date.now() / 1000;
  } catch {
    return 0;
  }
}

export async function refreshTokens(refreshToken: string): Promise<TokenPair | null> {
  const response = await fetch(`${BACKEND_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  return response.ok ? ((await response.json()) as TokenPair) : null;
}

/**
 * A usable access token, refreshing it first when it is missing or about to expire.
 * Refreshing *before* forwarding means request bodies (uploads) are streamed once, never replayed.
 */
export async function getAccessToken(): Promise<{ token?: string; refreshed?: TokenPair }> {
  const { accessToken, refreshToken } = await readSession();
  if (accessToken && secondsLeft(accessToken) > 30) return { token: accessToken };
  if (!refreshToken) return {};
  const refreshed = await refreshTokens(refreshToken);
  return refreshed ? { token: refreshed.access_token, refreshed } : {};
}

/** Reject state-changing requests from other sites (defence in depth on top of SameSite=Lax). */
export function isCrossSite(request: Request): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(request.method)) return false;
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return new URL(origin).host !== host;
  } catch {
    return true;
  }
}

/**
 * The browser's IP for the backend's rate limits and audit log. FastAPI only honours this header from
 * addresses in its TRUSTED_PROXIES setting (this Next.js server), so browsers can't spoof it.
 */
export function forwardedFor(request: Request): Record<string, string> {
  const chain = request.headers.get("x-forwarded-for") ?? request.headers.get("x-real-ip");
  return chain ? { "X-Forwarded-For": chain } : {};
}
