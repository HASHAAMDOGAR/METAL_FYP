import Link from "next/link";
import { API_URL } from "@/lib/api";

export default function Footer() {
  return (
    <footer className="mt-20 border-t border-white/10">
      <div className="container-x grid gap-8 py-12 sm:grid-cols-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-accent to-sky-400 text-xs font-black text-white">M</span>
            <span className="font-semibold text-white">MetalLLM Marketplace</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-slate-400">
            Apple Metal-powered LLM marketplace with MCP server support for macOS developers. UCP FYP — Group F25CS008.
          </p>
        </div>
        <div className="text-sm">
          <p className="mb-3 font-semibold text-white">Explore</p>
          <ul className="space-y-2 text-slate-400">
            <li><Link href="/marketplace" className="hover:text-white">Marketplace</Link></li>
            <li><Link href="/how-it-works" className="hover:text-white">How it works</Link></li>
            <li><Link href="/playground" className="hover:text-white">Inference playground</Link></li>
          </ul>
        </div>
        <div className="text-sm">
          <p className="mb-3 font-semibold text-white">Backend</p>
          <ul className="space-y-2 text-slate-400">
            <li><a href={`${API_URL}/docs`} target="_blank" rel="noreferrer" className="hover:text-white">API docs (Swagger)</a></li>
            <li><a href={`${API_URL}/readyz`} target="_blank" rel="noreferrer" className="hover:text-white">Health / readiness</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/5 py-5 text-center text-xs text-slate-500">
        © 2026 MetalLLM Marketplace · Built with FastAPI · MongoDB Atlas · Cloudflare R2 · Modal
      </div>
    </footer>
  );
}
