import { ReactNode } from "react";

export function Card({ children, className = "", hover = false }: { children: ReactNode; className?: string; hover?: boolean }) {
  return <div className={`card ${hover ? "card-hover" : ""} ${className}`}>{children}</div>;
}

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "accent" | "green" | "amber" }) {
  const tones: Record<string, string> = {
    default: "badge",
    accent: "badge border-accent/40 text-accent-glow bg-accent/10",
    green: "badge border-emerald-500/30 text-emerald-300 bg-emerald-500/10",
    amber: "badge border-amber-500/30 text-amber-300 bg-amber-500/10",
  };
  return <span className={tones[tone]}>{children}</span>;
}

export function Section({ title, kicker, children }: { title: string; kicker?: string; children: ReactNode }) {
  return (
    <section className="py-16">
      <div className="container-x">
        {kicker && (
          <span className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-accent-glow">
            {kicker}
          </span>
        )}
        <h2 className="mb-9 text-3xl font-bold text-white sm:text-4xl">{title}</h2>
        {children}
      </div>
    </section>
  );
}

export function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="card card-hover p-5">
      <div className="text-2xl font-bold gradient-text">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{label}</div>
    </div>
  );
}

export function CodeBlock({ children }: { children: string }) {
  return <pre className="codeblock">{children}</pre>;
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-accent" />
    </div>
  );
}
