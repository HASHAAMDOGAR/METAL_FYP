"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [publisher, setPublisher] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await register(email, username, password, publisher);
      router.push("/dashboard");
    } catch (e: any) {
      setErr(e.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container-x relative flex justify-center py-20">
      <div className="pointer-events-none absolute top-10 left-1/2 -z-10 h-72 w-96 -translate-x-1/2 rounded-full bg-accent/20 blur-[100px]" />
      <Card className="w-full max-w-md p-8">
        <div className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-accent to-sky-400 text-lg font-black text-white shadow-lg shadow-accent/30">M</div>
        <h1 className="text-2xl font-bold text-white">Create your account</h1>
        <p className="mt-1 text-sm text-slate-400">Free — no payment required.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="label">Username</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="at least 3 characters" />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="at least 8 characters" />
          </div>
          <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-ink-900/40 p-3 text-sm text-slate-300">
            <input type="checkbox" checked={publisher} onChange={(e) => setPublisher(e.target.checked)} className="h-4 w-4 accent-[#7c6cff]" />
            Also register as a Model Developer (publisher)
          </label>
          {err && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{err}</p>}
          <button className="btn-primary w-full" disabled={loading}>{loading ? "Creating…" : "Create account"}</button>
        </form>
        <p className="mt-5 text-center text-sm text-slate-400">
          Already have one? <Link href="/login" className="text-accent-glow hover:underline">Sign in</Link>
        </p>
      </Card>
    </div>
  );
}
