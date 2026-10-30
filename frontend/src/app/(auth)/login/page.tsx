"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, Card, ErrorText, Field, Input } from "@/components/ui";
import { authRequest } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    setError(null);
    try {
      await authRequest("login", { email: form.get("email"), password: form.get("password") });
      // Only allow same-site paths, so ?next= can't be used as an open redirect.
      router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/");
      router.refresh();
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  }

  return (
    <Card className="p-6">
      <form onSubmit={onSubmit} className="space-y-4">
        <h1 className="text-base font-semibold">Sign in</h1>
        <Field label="Email">
          <Input name="email" type="email" autoComplete="email" required autoFocus />
        </Field>
        <Field label="Password">
          <Input name="password" type="password" autoComplete="current-password" required />
        </Field>
        <ErrorText error={error} />
        <Button type="submit" loading={loading} className="w-full">
          Sign in
        </Button>
        <p className="text-center text-sm text-slate-500">
          New here?{" "}
          <Link href="/register" className="font-medium text-indigo-600 hover:text-indigo-500">
            Create an account
          </Link>
        </p>
      </form>
    </Card>
  );
}
