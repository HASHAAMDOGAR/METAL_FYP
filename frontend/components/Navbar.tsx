"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "Home" },
  { href: "/marketplace", label: "Marketplace" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/playground", label: "Playground" },
];

export default function Navbar() {
  const path = usePathname();
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-ink-950/70 backdrop-blur-xl">
      <nav className="container-x flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-sky-400 text-sm font-black text-white">M</span>
          <span className="font-semibold text-white">Metal<span className="text-accent-glow">LLM</span></span>
        </Link>
        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                path === l.href ? "text-white bg-white/5" : "text-slate-400 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Link href="/dashboard" className="btn-ghost py-2">Dashboard</Link>
              <button onClick={logout} className="text-sm text-slate-400 hover:text-white px-2">Sign out</button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-slate-300 hover:text-white px-3">Sign in</Link>
              <Link href="/register" className="btn-primary py-2">Get started</Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
