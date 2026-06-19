"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "Home" },
  { href: "/marketplace", label: "Marketplace" },
  { href: "/cloud", label: "Cloud Models" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/playground", label: "Playground" },
];

export default function Navbar() {
  const path = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-ink-950/70 backdrop-blur-xl">
      <nav className="container-x flex h-16 items-center justify-between">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-accent to-sky-400 text-sm font-black text-white shadow-lg shadow-accent/30 transition group-hover:shadow-accent/50">
            M
            <span className="absolute inset-0 -z-10 rounded-xl bg-accent/40 blur-md transition group-hover:bg-accent/60" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-white">
            Metal<span className="text-accent-glow">LLM</span>
          </span>
        </Link>

        <div className="hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 md:flex">
          {links.map((l) => {
            const active = isActive(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`relative rounded-full px-3.5 py-1.5 text-sm transition ${
                  active ? "text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {active && <span className="absolute inset-0 -z-0 rounded-full bg-gradient-to-br from-accent/25 to-sky-500/15 ring-1 ring-accent/30" />}
                <span className="relative z-10">{l.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 md:flex">
            {user ? (
              <>
                <Link href="/dashboard" className="btn-ghost py-2">Dashboard</Link>
                <button onClick={logout} className="px-2 text-sm text-slate-400 transition hover:text-white">Sign out</button>
              </>
            ) : (
              <>
                <Link href="/login" className="px-3 text-sm text-slate-300 transition hover:text-white">Sign in</Link>
                <Link href="/register" className="btn-primary py-2">Get started</Link>
              </>
            )}
          </div>
          <button
            onClick={() => setOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 text-slate-300 md:hidden"
            aria-label="Menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d={open ? "M6 18 18 6M6 6l12 12" : "M4 7h16M4 12h16M4 17h16"} />
            </svg>
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-white/10 bg-ink-950/95 px-5 py-3 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className={`rounded-lg px-3 py-2 text-sm ${isActive(l.href) ? "bg-white/5 text-white" : "text-slate-400"}`}
              >
                {l.label}
              </Link>
            ))}
            <div className="mt-2 flex gap-2 border-t border-white/10 pt-3">
              {user ? (
                <>
                  <Link href="/dashboard" onClick={() => setOpen(false)} className="btn-ghost flex-1 py-2">Dashboard</Link>
                  <button onClick={() => { logout(); setOpen(false); }} className="btn-ghost py-2">Sign out</button>
                </>
              ) : (
                <>
                  <Link href="/login" onClick={() => setOpen(false)} className="btn-ghost flex-1 py-2">Sign in</Link>
                  <Link href="/register" onClick={() => setOpen(false)} className="btn-primary flex-1 py-2">Get started</Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
