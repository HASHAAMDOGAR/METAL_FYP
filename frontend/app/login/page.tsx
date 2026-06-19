"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(id, pw);
      router.push("/dashboard");
    } catch (e: any) {
      setErr(e.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container-x relative flex justify-center py-20">
      <div className="pointer-events-none absolute top-10 left-1/2 -z-10 h-72 w-96 -translate-x-1/2 rounded-full bg-accent/20 blur-[100px]" />
      <Card className="w-full max-w-md p-8">
        <div className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-accent to-sky-400 text-lg font-black text-white shadow-lg shadow-accent/30">M</div>
        <h1 className="text-2xl font-bold text-white">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-400">Sign in to manage licenses and run inference.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label className="label">Email or username</label>
            <input className="input" value={id} onChange={(e) => setId(e.target.value)} placeholder="admin@metal.dev" />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="••••••••" />
          </div>
          {err && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{err}</p>}
          <button className="btn-primary w-full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="mt-5 text-center text-sm text-slate-400">
          No account? <Link href="/register" className="text-accent-glow hover:underline">Create one</Link>
        </p>
        <p className="mt-3 rounded-lg border border-white/10 bg-ink-900/40 p-3 text-center text-xs text-slate-500">
          Demo admin: <span className="text-slate-300">admin@metal.dev</span> / <span className="text-slate-300">admin12345</span>
        </p>
      </Card>
    </div>
  );
}
