"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api, CloudModel } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Msg = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "Explain the Apple Metal API in two sentences.",
  "Write a haiku about GPUs.",
  "Give me 3 startup ideas using on-device AI.",
  "Summarize quantum computing for a 10-year-old.",
];

const TOKEN_PRESETS: { label: string; value: number }[] = [
  { label: "512", value: 512 },
  { label: "1K", value: 1024 },
  { label: "4K", value: 4096 },
  { label: "∞", value: 0 },
];

// Deterministic gradient + initials so every model gets a stable, colorful avatar.
function hue(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
}
function avatarStyle(s: string): React.CSSProperties {
  const h = hue(s);
  return { backgroundImage: `linear-gradient(135deg, hsl(${h} 75% 58%), hsl(${(h + 55) % 360} 70% 46%))` };
}
function initials(name: string) {
  const p = name.replace(/[^a-zA-Z0-9 ]/g, " ").trim().split(/\s+/);
  return ((p[0]?.[0] || "") + (p[1]?.[0] || "")).toUpperCase() || "M";
}

function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  return (
    <span
      style={{ ...avatarStyle(name), width: size, height: size }}
      className="grid shrink-0 place-items-center rounded-xl text-xs font-bold text-white shadow-lg"
    >
      {initials(name)}
    </span>
  );
}

export default function CloudModels() {
  const { user } = useAuth();
  const [models, setModels] = useState<CloudModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState("");

  const [q, setQ] = useState("");
  const [readyOnly, setReadyOnly] = useState(true);

  const [selected, setSelected] = useState<CloudModel | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [maxTokens, setMaxTokens] = useState(1024);
  const [busy, setBusy] = useState(false);
  const [chatErr, setChatErr] = useState("");
  const [lastStats, setLastStats] = useState<{ tokens_generated: number; prompt_tokens: number } | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listCloudModels();
        setModels(list);
        setSelected(list.find((m) => m.chattable) || list[0] || null);
      } catch (e: any) {
        setLoadErr(e.message || "Failed to load models");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return models.filter((m) => {
      if (readyOnly && !m.chattable) return false;
      if (!needle) return true;
      return (
        m.name.toLowerCase().includes(needle) ||
        m.id.toLowerCase().includes(needle) ||
        (m.organization || "").toLowerCase().includes(needle)
      );
    });
  }, [models, q, readyOnly]);

  const readyCount = useMemo(() => models.filter((m) => m.chattable).length, [models]);

  function selectModel(m: CloudModel) {
    if (m.id === selected?.id) return;
    setSelected(m);
    setMessages([]);
    setChatErr("");
    setLastStats(null);
  }

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!selected || !content) return;
    setChatErr("");
    if (!user) {
      setChatErr("Sign in to run a model.");
      return;
    }
    const userMsg: Msg = { role: "user", content };
    const thread = [...messages, userMsg];
    setMessages(thread);
    setInput("");
    setBusy(true);
    try {
      const r = await api.cloudChat({ model: selected.id, messages: thread, max_tokens: maxTokens });
      setMessages([...thread, { role: "assistant", content: r.output }]);
      setLastStats({ tokens_generated: r.tokens_generated, prompt_tokens: r.prompt_tokens });
    } catch (e: any) {
      setChatErr(e.message || "Inference failed");
      setMessages(messages);
      setInput(userMsg.content);
    } finally {
      setBusy(false);
    }
  }

  const canSend = !!selected && selected.chattable !== false && !busy;

  return (
    <div className="relative">
      {/* Hero */}
      <div className="relative overflow-hidden border-b border-white/5">
        <div className="pointer-events-none absolute -top-32 right-0 h-80 w-80 rounded-full bg-accent/20 blur-[100px]" />
        <div className="pointer-events-none absolute -top-20 left-10 h-72 w-72 rounded-full bg-sky-500/10 blur-[100px]" />
        <div className="container-x relative py-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent-glow">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            Managed GPU Cloud · live
          </div>
          <h1 className="mt-5 text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
            Explore <span className="gradient-text">Cloud Models</span>
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-300">
            Hundreds of frontier and open models, hosted on our managed GPU cloud. Pick one and start
            chatting instantly — no download, no setup.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <HeroStat value={loading ? "—" : `${models.length}`} label="hosted models" />
            <HeroStat value={loading ? "—" : `${readyCount}`} label="ready to run" tone="green" />
            <HeroStat value="0s" label="setup time" />
            <HeroStat value="∞" label="token limit" />
          </div>
        </div>
      </div>

      <div className="container-x py-8">
        {loadErr && <p className="rounded-xl bg-red-500/10 p-4 text-red-300">{loadErr}</p>}

        {loading ? (
          <CatalogSkeleton />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
            {/* ---------- Catalog ---------- */}
            <div className="card flex h-[74vh] flex-col overflow-hidden">
              <div className="border-b border-white/5 p-4">
                <div className="relative">
                  <svg className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
                  </svg>
                  <input
                    className="input pl-10"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search hundreds of models…"
                  />
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex gap-1.5">
                    <FilterChip active={readyOnly} onClick={() => setReadyOnly(true)}>⚡ Ready</FilterChip>
                    <FilterChip active={!readyOnly} onClick={() => setReadyOnly(false)}>All models</FilterChip>
                  </div>
                  <span className="text-xs text-slate-500">{filtered.length} shown</span>
                </div>
              </div>

              <div className="scroll-thin flex-1 space-y-1.5 overflow-y-auto p-3">
                {filtered.map((m, i) => {
                  const active = selected?.id === m.id;
                  return (
                    <button
                      key={m.id}
                      onClick={() => selectModel(m)}
                      style={{ animationDelay: `${Math.min(i, 14) * 18}ms` }}
                      className={`animate-fade-up group flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all duration-200 ${
                        active
                          ? "border-accent/60 bg-accent/10 shadow-[0_0_0_1px_rgba(124,108,255,0.4),0_8px_30px_-12px_rgba(124,108,255,0.6)]"
                          : "border-transparent hover:border-white/10 hover:bg-white/[0.04]"
                      }`}
                    >
                      <Avatar name={m.name} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`truncate text-sm font-semibold ${active ? "text-white" : "text-slate-200 group-hover:text-white"}`}>
                            {m.name}
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                          <span className="truncate">{m.organization || "Community"}</span>
                          {m.context_length ? <span>· {(m.context_length / 1000).toFixed(0)}K ctx</span> : null}
                        </div>
                      </div>
                      {m.chattable ? (
                        <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                          <span className="ready-dot inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                          ready
                        </span>
                      ) : (
                        <span className="rounded-full bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                          dedicated
                        </span>
                      )}
                    </button>
                  );
                })}
                {filtered.length === 0 && (
                  <p className="py-10 text-center text-sm text-slate-500">No models match “{q}”.</p>
                )}
              </div>
            </div>

            {/* ---------- Chat ---------- */}
            <div className="card flex h-[74vh] flex-col overflow-hidden">
              {/* header */}
              <div className="flex items-center justify-between gap-3 border-b border-white/5 bg-white/[0.02] p-4">
                <div className="flex min-w-0 items-center gap-3">
                  {selected && <Avatar name={selected.name} size={44} />}
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-white">{selected?.name || "Select a model"}</div>
                    <div className="truncate text-xs text-slate-500">
                      {selected
                        ? [selected.organization, selected.type, selected.context_length ? `${(selected.context_length / 1000).toFixed(0)}K ctx` : null]
                            .filter(Boolean)
                            .join(" · ")
                        : "Pick a model from the list"}
                    </div>
                  </div>
                </div>
                {messages.length > 0 && (
                  <button
                    onClick={() => { setMessages([]); setLastStats(null); setChatErr(""); }}
                    className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-slate-400 transition hover:bg-white/5 hover:text-white"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* thread */}
              <div ref={threadRef} className="scroll-thin flex-1 space-y-4 overflow-y-auto p-4">
                {messages.length === 0 && !busy && (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    {selected && <Avatar name={selected.name} size={56} />}
                    <p className="mt-4 text-sm text-slate-400">
                      Chat with <span className="font-medium text-slate-200">{selected?.name || "a model"}</span>
                    </p>
                    {selected?.chattable === false ? (
                      <p className="mt-2 max-w-xs text-xs text-amber-300/80">
                        This model needs a dedicated deployment. Pick one marked <b>ready</b> to chat instantly.
                      </p>
                    ) : (
                      <div className="mt-5 flex max-w-md flex-wrap justify-center gap-2">
                        {SUGGESTIONS.map((s) => (
                          <button
                            key={s}
                            onClick={() => (user ? send(s) : setChatErr("Sign in to run a model."))}
                            className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:bg-accent/10 hover:text-white"
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {messages.map((m, i) => (
                  <div key={i} className={`flex animate-pop items-end gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                    {m.role === "assistant" && selected ? (
                      <Avatar name={selected.name} size={30} />
                    ) : (
                      <span className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent to-sky-400 text-[10px] font-bold text-white shadow-lg">
                        You
                      </span>
                    )}
                    <div
                      className={`max-w-[82%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
                        m.role === "user"
                          ? "rounded-br-md bg-gradient-to-br from-accent to-accent-glow text-white"
                          : "rounded-bl-md border border-white/10 bg-white/[0.04] text-slate-200"
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}

                {busy && (
                  <div className="flex animate-pop items-end gap-2.5">
                    {selected && <Avatar name={selected.name} size={30} />}
                    <div className="rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.04] px-4 py-3">
                      <span className="flex gap-1">
                        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
                        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" style={{ animationDelay: "200ms" }} />
                        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" style={{ animationDelay: "400ms" }} />
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* composer */}
              <div className="border-t border-white/5 bg-white/[0.02] p-4">
                {chatErr && (
                  <p className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">{chatErr}</p>
                )}
                {lastStats && !busy && !chatErr && (
                  <div className="mb-3 flex items-center gap-2 text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-300">✓ cloud</span>
                    <span>{lastStats.tokens_generated} tokens generated</span>
                  </div>
                )}

                <div className="relative">
                  <textarea
                    className="input min-h-[56px] resize-none pr-4"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={
                      !user
                        ? "Sign in to start chatting…"
                        : selected?.chattable === false
                        ? "This model needs a dedicated deployment"
                        : "Send a message…  (⌘/Ctrl + Enter)"
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
                    }}
                  />
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] uppercase tracking-wide text-slate-500">Tokens</span>
                    {TOKEN_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setMaxTokens(p.value)}
                        className={`rounded-lg px-2 py-1 text-xs font-medium transition ${
                          maxTokens === p.value
                            ? "bg-accent/20 text-accent-glow ring-1 ring-accent/40"
                            : "text-slate-400 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>

                  {!user ? (
                    <Link href="/login" className="btn-primary ml-auto">Sign in to chat</Link>
                  ) : (
                    <button
                      onClick={() => send()}
                      disabled={!canSend || !input.trim()}
                      className="btn-primary ml-auto gap-2"
                    >
                      {busy ? "Generating…" : "Send"}
                      {!busy && (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" />
                        </svg>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HeroStat({ value, label, tone }: { value: string; label: string; tone?: "green" }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 backdrop-blur-sm">
      <div className={`text-xl font-bold ${tone === "green" ? "text-emerald-300" : "gradient-text"}`}>{value}</div>
      <div className="text-[11px] text-slate-400">{label}</div>
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
        active ? "bg-accent/20 text-accent-glow ring-1 ring-accent/40" : "text-slate-400 hover:bg-white/5 hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}

function CatalogSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
      <div className="card h-[74vh] space-y-2 p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl p-3">
            <div className="h-10 w-10 animate-pulse rounded-xl bg-white/5" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-1/2 animate-pulse rounded bg-white/5" />
              <div className="h-2.5 w-1/3 animate-pulse rounded bg-white/5" />
            </div>
          </div>
        ))}
      </div>
      <div className="card grid h-[74vh] place-items-center">
        <div className="text-sm text-slate-500">Loading models…</div>
      </div>
    </div>
  );
}
