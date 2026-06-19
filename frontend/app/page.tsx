import Link from "next/link";
import { Card, Section, Stat, Badge } from "@/components/ui";

const innovations = [
  {
    title: "Performance",
    body: "Metal-accelerated inference runs LLMs directly on the Apple Silicon GPU — targeting 30+ tokens/sec for a 7B model on an M2, far beyond CPU-bound paths.",
    icon: "⚡",
  },
  {
    title: "Security & Licensing",
    body: "A simplified DRM: every model is licensed to a user and bound to specific devices. The local MCP server verifies the license before loading weights.",
    icon: "🔐",
  },
  {
    title: "Ecosystem & SDK",
    body: "A plug-and-play developer SDK speaks the MCP protocol to the local daemon — making native, on-device LLM calls as simple as a function call.",
    icon: "🧩",
  },
];

const stack = [
  { k: "API", v: "FastAPI (Python)" },
  { k: "Database", v: "MongoDB Atlas" },
  { k: "Storage", v: "Cloudflare R2" },
  { k: "Cloud GPU", v: "Modal" },
  { k: "Local engine", v: "Apple Metal" },
  { k: "Protocol", v: "MCP" },
];

export default function Home() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 right-0 h-[30rem] w-[30rem] rounded-full bg-accent/25 blur-[120px]" />
        <div className="pointer-events-none absolute top-10 -left-20 h-[24rem] w-[24rem] rounded-full bg-sky-500/15 blur-[120px]" />
        <div className="container-x grid items-center gap-10 py-20 lg:grid-cols-2 lg:py-28">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent-glow">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              UCP Final Year Project · F25CS008
            </div>
            <h1 className="mt-6 text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
              Run <span className="gradient-text">LLMs natively</span> on Apple Silicon
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
              Discover, license, and run large language models accelerated by the Apple Metal GPU —
              with a seamless managed cloud fallback when local Metal isn&apos;t available.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/cloud" className="btn-primary">Try Cloud Models →</Link>
              <Link href="/marketplace" className="btn-ghost">Browse the marketplace</Link>
            </div>
            <div className="mt-10 grid max-w-md grid-cols-3 gap-3">
              <Stat value="30+" label="tokens/sec on M2 (7B)" />
              <Stat value="2×" label="faster vs CPU baseline" />
              <Stat value="< 5s" label="model deploy time" />
            </div>
          </div>

          {/* Architecture card */}
          <div className="relative">
            <Card className="animate-float p-6">
              <p className="mb-4 text-sm font-semibold text-slate-400">End-to-end architecture</p>
              <div className="space-y-3 text-sm">
                <Flow from="Web / SDK client" to="Marketplace API" note="browse · license · verify" />
                <Flow from="Marketplace API" to="MongoDB Atlas" note="users · models · licenses" />
                <Flow from="Marketplace API" to="Cloudflare R2" note="GGUF model weights" />
                <Flow from="MCP Server (macOS)" to="Metal Engine" note="on-device GPU inference" tone="green" />
                <Flow from="No local Metal?" to="Modal GPU" note="cloud fallback inference" tone="amber" />
              </div>
            </Card>
            <div className="pointer-events-none absolute -inset-6 -z-10 rounded-[2rem] bg-accent/20 blur-3xl" />
          </div>
        </div>
      </section>

      {/* Problem / purpose */}
      <Section kicker="The purpose" title="Why this project exists">
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-white">The problem</h3>
            <p className="mt-2 text-slate-300">
              Integrating LLMs into native macOS apps is fragmented. Tools are scattered, most ignore the Apple Metal GPU,
              and there is no trusted marketplace to discover, license, and distribute models for the Mac.
            </p>
          </Card>
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-white">The solution</h3>
            <p className="mt-2 text-slate-300">
              A dual-component platform: a hosted <b>Marketplace</b> for distribution and licensing, plus a local <b>MCP
              Server</b> that loads and runs models on the Metal GPU — exposed to apps through a simple SDK.
            </p>
          </Card>
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-white">This build</h3>
            <p className="mt-2 text-slate-300">
              Free models only (no payments), simplified licensing with device binding, and a <b>Modal</b> cloud GPU
              fallback so inference works even on hardware without Apple Silicon Metal.
            </p>
          </Card>
        </div>
      </Section>

      {/* Innovations */}
      <Section kicker="Three core innovations" title="What makes it different">
        <div className="grid gap-6 md:grid-cols-3">
          {innovations.map((i) => (
            <Card key={i.title} hover className="group p-6">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-accent/30 to-sky-500/20 text-2xl ring-1 ring-white/10 transition group-hover:from-accent/40 group-hover:to-sky-500/30">
                {i.icon}
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">{i.title}</h3>
              <p className="mt-2 text-slate-300">{i.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Stack */}
      <Section kicker="Built with" title="The technology stack">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {stack.map((s) => (
            <Card key={s.k} className="p-5 text-center">
              <div className="text-xs uppercase tracking-wide text-slate-500">{s.k}</div>
              <div className="mt-1 text-sm font-semibold text-white">{s.v}</div>
            </Card>
          ))}
        </div>
      </Section>

      {/* Closing CTA */}
      <section className="pb-24">
        <div className="container-x">
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-accent/15 via-white/[0.03] to-sky-500/10 p-10 text-center sm:p-14">
            <div className="pointer-events-none absolute -top-20 left-1/2 h-56 w-[34rem] -translate-x-1/2 rounded-full bg-accent/25 blur-[100px]" />
            <h2 className="relative text-3xl font-bold text-white sm:text-4xl">
              Start running models in seconds
            </h2>
            <p className="relative mx-auto mt-4 max-w-xl text-slate-300">
              Create a free account, then chat with hundreds of hosted models or license one to run on-device.
            </p>
            <div className="relative mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/register" className="btn-primary">Create a free account</Link>
              <Link href="/cloud" className="btn-ghost">Explore Cloud Models</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function Flow({ from, to, note, tone = "default" }: { from: string; to: string; note: string; tone?: "default" | "green" | "amber" }) {
  const dot = tone === "green" ? "bg-emerald-400" : tone === "amber" ? "bg-amber-400" : "bg-accent";
  return (
    <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-ink-900/50 p-3">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-slate-200">
          <span className="truncate font-medium">{from}</span>
          <span className="text-slate-500">→</span>
          <span className="truncate font-medium">{to}</span>
        </div>
        <div className="text-xs text-slate-500">{note}</div>
      </div>
    </div>
  );
}
