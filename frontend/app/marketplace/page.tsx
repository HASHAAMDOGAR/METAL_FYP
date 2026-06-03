"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ModelListItem } from "@/lib/api";
import { Card, Badge, Spinner } from "@/components/ui";

const ARCHS = ["", "llama", "mistral", "qwen", "phi", "gemma"];
const SORTS = [
  ["newest", "Newest"],
  ["downloads", "Most downloaded"],
  ["rating", "Top rated"],
];

export default function Marketplace() {
  const [items, setItems] = useState<ModelListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [arch, setArch] = useState("");
  const [sort, setSort] = useState("newest");
  const [err, setErr] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const params: Record<string, string> = { sort, page_size: "24" };
      if (q) params.q = q;
      if (arch) params.architecture = arch;
      const res = await api.listModels(params);
      setItems(res.items);
      setTotal(res.total);
    } catch (e: any) {
      setErr(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [arch, sort]);

  return (
    <div className="container-x py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold text-white">Model Marketplace</h1>
          <p className="mt-2 text-slate-400">{total} approved model{total === 1 ? "" : "s"} ready to license & run.</p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
          className="flex gap-2"
        >
          <input className="input w-64" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search models…" />
          <button className="btn-primary">Search</button>
        </form>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {ARCHS.map((a) => (
          <button
            key={a || "all"}
            onClick={() => setArch(a)}
            className={`badge ${arch === a ? "border-accent/50 bg-accent/15 text-accent-glow" : ""}`}
          >
            {a || "All architectures"}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          {SORTS.map(([v, label]) => (
            <button key={v} onClick={() => setSort(v)} className={`badge ${sort === v ? "border-accent/50 bg-accent/15 text-accent-glow" : ""}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {err && <p className="mt-8 rounded-xl bg-red-500/10 p-4 text-red-300">{err}</p>}
      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="mt-16 text-center text-slate-400">No models match your search.</p>
      ) : (
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((m) => (
            <Link key={m.id} href={`/marketplace/${m.slug}`}>
              <Card hover className="h-full p-5">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-white">{m.name}</h3>
                  <Badge tone="green">free</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge tone="accent">{m.architecture}</Badge>
                  {m.quantization && <Badge>{m.quantization}</Badge>}
                  {m.param_count_b && <Badge>{m.param_count_b}B</Badge>}
                </div>
                <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                  <span>⭐ {m.metrics.rating_avg.toFixed(1)} ({m.metrics.rating_count})</span>
                  <span>⬇ {m.metrics.downloads}</span>
                  {m.metrics.tokens_per_sec_m2 && <span>{m.metrics.tokens_per_sec_m2} tok/s</span>}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
