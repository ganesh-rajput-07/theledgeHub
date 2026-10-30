"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, Card, ErrorText, Field, Input } from "@/components/ui";
import { authRequest } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    setError(null);
    try {
      await authRequest("register", Object.fromEntries(form));
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  }

  return (
    <Card className="p-6">
      <form onSubmit={onSubmit} className="space-y-4">
        <h1 className="text-base font-semibold">Create your account</h1>
        <Field label="Full name">
          <Input name="full_name" autoComplete="name" />
        </Field>
        <Field label="Work email">
          <Input name="email" type="email" autoComplete="email" required />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <Input name="password" type="password" autoComplete="new-password" minLength={8} required />
        </Field>
        <Field label="Organization" hint="Your company or team. A “General” workspace is created for you.">
          <Input name="organization_name" placeholder="Acme Inc." required />
        </Field>
        <ErrorText error={error} />
        <Button type="submit" loading={loading} className="w-full">
          Create account
        </Button>
        <p className="text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
            Sign in
          </Link>
        </p>
      </form>
    </Card>
  );
}
