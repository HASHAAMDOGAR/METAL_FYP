import Link from "next/link";
import { API_URL } from "@/lib/api";

export default function Footer() {
  return (
    <footer className="relative mt-24 overflow-hidden border-t border-white/10">
      <div className="pointer-events-none absolute -bottom-24 left-1/2 h-56 w-[40rem] -translate-x-1/2 rounded-full bg-accent/15 blur-[100px]" />
      <div className="container-x relative grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-accent to-sky-400 text-xs font-black text-white shadow-lg shadow-accent/30">M</span>
            <span className="font-semibold text-white">MetalLLM Marketplace</span>
          </div>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
            Apple Metal-powered LLM marketplace with MCP server support for macOS developers.
            Discover, license, and run models on-device — with a managed GPU cloud fallback.
          </p>
          <p className="mt-4 text-xs text-slate-500">UCP Final Year Project · Group F25CS008</p>
        </div>
        <div className="text-sm">
          <p className="mb-3 font-semibold text-white">Explore</p>
          <ul className="space-y-2.5 text-slate-400">
            <li><Link href="/marketplace" className="transition hover:text-accent-glow">Marketplace</Link></li>
            <li><Link href="/cloud" className="transition hover:text-accent-glow">Cloud Models</Link></li>
            <li><Link href="/how-it-works" className="transition hover:text-accent-glow">How it works</Link></li>
            <li><Link href="/playground" className="transition hover:text-accent-glow">Inference playground</Link></li>
          </ul>
        </div>
        <div className="text-sm">
          <p className="mb-3 font-semibold text-white">Backend</p>
          <ul className="space-y-2.5 text-slate-400">
            <li><a href={`${API_URL}/docs`} target="_blank" rel="noreferrer" className="transition hover:text-accent-glow">API docs (Swagger)</a></li>
            <li><a href={`${API_URL}/readyz`} target="_blank" rel="noreferrer" className="transition hover:text-accent-glow">Health / readiness</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/5 py-5 text-center text-xs text-slate-500">
        © 2026 MetalLLM Marketplace · Built with FastAPI · MongoDB Atlas · Cloudflare R2 · Modal
      </div>
    </footer>
  );
}
