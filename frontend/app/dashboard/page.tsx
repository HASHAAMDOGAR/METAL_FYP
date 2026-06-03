"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, License } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Badge, Spinner } from "@/components/ui";

export default function Dashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [licenses, setLicenses] = useState<License[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  async function load() {
    try {
      setLicenses(await api.myLicenses());
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (user) load();
  }, [user]);

  async function bind(key: string) {
    const deviceId = `web-${Math.random().toString(36).slice(2, 10)}`;
    try {
      await api.bindDevice(key, { device_id: deviceId, device_name: "Web device", platform: navigator.platform });
      load();
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  async function unbind(key: string, deviceId: string) {
    try {
      await api.unbindDevice(key, deviceId);
      load();
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  async function download(modelId: string, key: string, deviceId?: string) {
    try {
      const d = await api.download(modelId, deviceId);
      setMsg(`Download URL ready (expires in ${d.expires_in}s). sha256 ${d.sha256?.slice(0, 12)}…`);
      window.open(d.download_url, "_blank");
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  if (authLoading || loading) return <Spinner />;

  return (
    <div className="container-x py-14">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Your dashboard</h1>
          <p className="mt-1 text-slate-400">
            Signed in as <span className="text-slate-200">{user?.username}</span> ·{" "}
            {user?.roles.map((r) => (
              <Badge key={r}>{r}</Badge>
            ))}
          </p>
        </div>
        <Link href="/marketplace" className="btn-ghost">Browse models</Link>
      </div>

      {msg && <p className="mt-6 rounded-xl bg-white/5 p-3 text-sm text-slate-300 break-words">{msg}</p>}

      <h2 className="mt-10 text-xl font-semibold text-white">Your licenses ({licenses.length})</h2>
      {licenses.length === 0 ? (
        <Card className="mt-4 p-8 text-center">
          <p className="text-slate-400">No licenses yet.</p>
          <Link href="/marketplace" className="btn-primary mt-4 inline-flex">Acquire your first model</Link>
        </Card>
      ) : (
        <div className="mt-4 space-y-4">
          {licenses.map((l) => (
            <Card key={l.license_key} className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <code className="font-mono text-sm text-accent-glow">{l.license_key}</code>
                  <div className="mt-1 text-xs text-slate-400">
                    Model {l.model_id.slice(-6)} · <Badge tone={l.status === "active" ? "green" : "amber"}>{l.status}</Badge>{" "}
                    · {l.bound_device_count}/{l.max_devices} devices
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => bind(l.license_key)} disabled={l.bound_device_count >= l.max_devices} className="btn-ghost py-2">
                    Bind device
                  </button>
                  <button
                    onClick={() => download(l.model_id, l.license_key, l.devices[0]?.device_id)}
                    disabled={l.devices.length === 0}
                    className="btn-primary py-2"
                  >
                    Download
                  </button>
                </div>
              </div>

              {l.devices.length > 0 && (
                <div className="mt-4 space-y-2">
                  {l.devices.map((d) => (
                    <div key={d.device_id} className="flex items-center justify-between rounded-lg border border-white/10 bg-ink-900/40 px-3 py-2 text-xs">
                      <span className="text-slate-300">
                        🖥 {d.device_name || d.device_id} <span className="text-slate-500">· {d.platform}</span>
                      </span>
                      <button onClick={() => unbind(l.license_key, d.device_id)} className="text-red-300 hover:underline">
                        Unbind
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
