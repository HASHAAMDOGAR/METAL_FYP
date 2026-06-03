"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, ModelDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Badge, Spinner } from "@/components/ui";

export default function ModelPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [model, setModel] = useState<ModelDetail | null>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const m = await api.getModel(slug);
        setModel(m);
        const r = await api.listReviews(slug);
        setReviews(r.items);
      } catch (e: any) {
        setMsg(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [slug]);

  async function acquire() {
    if (!user) {
      router.push("/login");
      return;
    }
    if (!model) return;
    setBusy(true);
    setMsg("");
    try {
      const lic = await api.acquire(model.id);
      setMsg(`License acquired: ${lic.license_key}. Manage it in your dashboard.`);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;
  if (!model) return <p className="container-x py-20 text-center text-slate-400">{msg || "Model not found."}</p>;

  const a = model.artifact;
  const meta: [string, string][] = [
    ["Architecture", model.architecture],
    ["Quantization", model.quantization || "—"],
    ["Parameters", model.param_count_b ? `${model.param_count_b}B` : "—"],
    ["Context length", model.context_length ? `${model.context_length}` : "—"],
    ["Min RAM", model.min_ram_gb ? `${model.min_ram_gb} GB` : "—"],
    ["Format", model.file_format.toUpperCase()],
    ["Size", a.size_bytes ? `${(a.size_bytes / 1e9).toFixed(2)} GB` : "—"],
    ["Benchmark", model.metrics.tokens_per_sec_m2 ? `${model.metrics.tokens_per_sec_m2} tok/s (M2)` : "—"],
  ];

  return (
    <div className="container-x py-12">
      <Link href="/marketplace" className="text-sm text-slate-400 hover:text-white">← Back to marketplace</Link>

      <div className="mt-4 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-bold text-white">{model.name}</h1>
            <Badge tone="green">free</Badge>
            <Badge tone="accent">{model.architecture}</Badge>
          </div>
          <p className="mt-4 text-slate-300">{model.description || "No description provided."}</p>

          {model.tags.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {model.tags.map((t) => (
                <Badge key={t}>#{t}</Badge>
              ))}
            </div>
          )}

          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {meta.map(([k, v]) => (
              <Card key={k} className="p-4">
                <div className="text-xs text-slate-500">{k}</div>
                <div className="mt-1 text-sm font-semibold text-white">{v}</div>
              </Card>
            ))}
          </div>

          {/* Cloud inference availability */}
          <Card className="mt-6 p-5">
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${model.cloud_inference.enabled ? "bg-emerald-400" : "bg-slate-500"}`} />
              <span className="text-sm font-medium text-white">
                Cloud inference {model.cloud_inference.enabled ? "available" : "disabled"}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              {model.cloud_inference.enabled
                ? `Runs on Modal GPU as a fallback (ref: ${model.cloud_inference.served_model_ref}). Try it in the Playground.`
                : "This model runs locally on the Metal engine only."}
            </p>
          </Card>

          {/* Reviews */}
          <h2 className="mt-10 text-xl font-semibold text-white">Reviews ({reviews.length})</h2>
          <div className="mt-4 space-y-3">
            {reviews.length === 0 && <p className="text-sm text-slate-400">No reviews yet.</p>}
            {reviews.map((r) => (
              <Card key={r.id} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{r.title || "Review"}</span>
                  <span className="text-amber-300">{"★".repeat(r.rating)}<span className="text-slate-600">{"★".repeat(5 - r.rating)}</span></span>
                </div>
                {r.body && <p className="mt-1 text-sm text-slate-400">{r.body}</p>}
              </Card>
            ))}
          </div>
        </div>

        {/* Sidebar action */}
        <div>
          <Card className="sticky top-20 p-6">
            <div className="text-3xl font-bold gradient-text">Free</div>
            <p className="mt-1 text-sm text-slate-400">Licensed to you, bound to your devices.</p>
            <button onClick={acquire} disabled={busy} className="btn-primary mt-5 w-full">
              {busy ? "Acquiring…" : user ? "Acquire license" : "Sign in to acquire"}
            </button>
            {model.cloud_inference.enabled && (
              <Link href={`/playground?model=${model.slug}`} className="btn-ghost mt-3 w-full">Try in Playground</Link>
            )}
            {msg && <p className="mt-4 rounded-lg bg-white/5 p-3 text-xs text-slate-300 break-words">{msg}</p>}
            <div className="mt-6 space-y-2 text-xs text-slate-400">
              <div className="flex justify-between"><span>Downloads</span><span className="text-slate-200">{model.metrics.downloads}</span></div>
              <div className="flex justify-between"><span>Rating</span><span className="text-slate-200">{model.metrics.rating_avg.toFixed(1)} / 5</span></div>
              <div className="flex justify-between"><span>Status</span><span className="text-emerald-300">{model.status}</span></div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
