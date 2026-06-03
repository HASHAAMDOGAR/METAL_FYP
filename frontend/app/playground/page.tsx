"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ModelListItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Badge, Spinner } from "@/components/ui";

function Playground() {
  const { user } = useAuth();
  const params = useSearchParams();
  const [models, setModels] = useState<ModelListItem[]>([]);
  const [modelId, setModelId] = useState("");
  const [prompt, setPrompt] = useState("Explain the Apple Metal API in one sentence.");
  const [maxTokens, setMaxTokens] = useState(64);
  const [out, setOut] = useState("");
  const [stats, setStats] = useState<{ tokens_generated: number; tokens_per_sec: number; path: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      const res = await api.listModels({ page_size: "50" });
      const cloud = res.items.filter((m) => true);
      setModels(cloud);
      const pre = params.get("model");
      const found = pre ? cloud.find((m) => m.slug === pre) : null;
      setModelId(found?.id || cloud[0]?.id || "");
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run() {
    setErr("");
    setOut("");
    setStats(null);
    if (!user) {
      setErr("Sign in first, then acquire a license for the model.");
      return;
    }
    setBusy(true);
    try {
      // ensure a license exists (idempotent), then run cloud inference
      await api.acquire(modelId).catch(() => {});
      const r = await api.inference({
        model_id: modelId,
        prompt,
        max_tokens: maxTokens,
        reason: "no_metal_device",
      });
      setOut(r.output);
      setStats({ tokens_generated: r.tokens_generated, tokens_per_sec: r.tokens_per_sec, path: r.path });
    } catch (e: any) {
      setErr(e.message || "Inference failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <label className="label">Model</label>
          <select className="input" value={modelId} onChange={(e) => setModelId(e.target.value)}>
            {models.map((m) => (
              <option key={m.id} value={m.id} className="bg-ink-900">
                {m.name}
              </option>
            ))}
          </select>

          <label className="label mt-4">Prompt</label>
          <textarea className="input min-h-[120px]" value={prompt} onChange={(e) => setPrompt(e.target.value)} />

          <label className="label mt-4">Max tokens: {maxTokens}</label>
          <input type="range" min={16} max={256} value={maxTokens} onChange={(e) => setMaxTokens(+e.target.value)} className="w-full accent-[#7c6cff]" />

          <button onClick={run} disabled={busy || !modelId} className="btn-primary mt-5 w-full">
            {busy ? "Generating on Modal GPU…" : "Run inference"}
          </button>
          {!user && (
            <p className="mt-3 text-center text-xs text-slate-400">
              <Link href="/login" className="text-accent-glow hover:underline">Sign in</Link> to run inference.
            </p>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <span className="label mb-0">Output</span>
            {stats && (
              <div className="flex gap-2">
                <Badge tone="green">{stats.path}</Badge>
                <Badge>{stats.tokens_generated} tok</Badge>
                <Badge>{stats.tokens_per_sec} tok/s</Badge>
              </div>
            )}
          </div>
          <div className="mt-3 min-h-[220px] rounded-xl border border-white/10 bg-ink-950/60 p-4 text-sm text-slate-200">
            {busy ? <Spinner /> : err ? <span className="text-red-300">{err}</span> : out ? <span className="whitespace-pre-wrap">{out}</span> : <span className="text-slate-500">Output will appear here…</span>}
          </div>
        </Card>
    </div>
  );
}

export default function Page() {
  return (
    <div className="container-x py-14">
      <Badge tone="accent">Cloud GPU · Modal fallback</Badge>
      <h1 className="mt-4 text-4xl font-bold text-white">Inference Playground</h1>
      <p className="mt-2 max-w-2xl text-slate-300">
        This runs the same path your app uses when local Apple Metal is unavailable: the request is license-checked and
        routed to a Modal GPU. The first call may cold-start the model (~30–60s); later calls are fast.
      </p>
      <Suspense fallback={<Spinner />}>
        <Playground />
      </Suspense>
    </div>
  );
}
