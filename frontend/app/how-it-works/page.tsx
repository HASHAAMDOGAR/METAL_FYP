import { Card, Badge, CodeBlock } from "@/components/ui";
import { API_URL } from "@/lib/api";

const services = [
  {
    name: "Authentication",
    tag: "auth",
    purpose: "Account creation and JWT-based sign-in for App Developers (consumers) and Model Developers (publishers).",
    endpoints: [
      ["POST", "/v1/auth/register", "Create an account (optionally as a publisher)"],
      ["POST", "/v1/auth/login", "Exchange credentials for access + refresh tokens"],
      ["POST", "/v1/auth/refresh", "Rotate the refresh token"],
      ["GET", "/v1/users/me", "Current profile"],
    ],
    how: "Register, then attach the returned access token as a Bearer header on every protected call. Tokens rotate; logout denylists the refresh token server-side.",
  },
  {
    name: "Catalog & Search",
    tag: "catalog",
    purpose: "Public browsing of approved models with full-text search, architecture/tag filters, and sorting.",
    endpoints: [
      ["GET", "/v1/models", "List/search models (q, architecture, tags, sort, page)"],
      ["GET", "/v1/models/{slug}", "Model detail incl. benchmarks & artifact info"],
      ["GET", "/v1/models/{slug}/reviews", "Community reviews"],
    ],
    how: "No auth needed to browse. Search uses a MongoDB text index; results are paginated and sortable by downloads, rating, or recency.",
  },
  {
    name: "Publisher",
    tag: "publisher",
    purpose: "Model Developers upload, manage, and monitor their GGUF models.",
    endpoints: [
      ["POST", "/v1/publisher/models", "Create a draft (metadata, free pricing)"],
      ["POST", "/v1/publisher/models/{id}/artifact", "Get a presigned upload URL"],
      ["POST", "/v1/publisher/models/{id}/submit", "Submit for admin review"],
      ["GET", "/v1/publisher/models/{id}/report", "Usage report (downloads, tokens/sec)"],
    ],
    how: "Create a draft → upload the GGUF straight to storage via a presigned URL (bytes never transit the API) → finalize with a checksum → submit. An admin approves before it appears in the catalog.",
  },
  {
    name: "Licensing & Devices",
    tag: "licenses",
    purpose: "Free entitlements bound to specific devices — the simplified DRM at the heart of the project.",
    endpoints: [
      ["POST", "/v1/models/{id}/acquire", "Issue a free license (idempotent)"],
      ["POST", "/v1/licenses/{key}/devices", "Bind a device (capped at max_devices)"],
      ["POST", "/v1/licenses/{key}/verify", "License check used by the MCP server"],
    ],
    how: "Acquire a license, bind your Mac's device id (cap of 3 by default), then the local MCP server calls verify before loading the model into the Metal engine.",
  },
  {
    name: "Downloads",
    tag: "downloads",
    purpose: "Secure, license-gated delivery of model weights.",
    endpoints: [["GET", "/v1/models/{id}/download", "Presigned URL + sha256 + size (active license required)"]],
    how: "With an active license, request a short-lived presigned download URL. The MCP server fetches the GGUF into local secure storage and verifies the sha256.",
  },
  {
    name: "Cloud Inference (Modal)",
    tag: "inference",
    purpose: "GPU fallback when local Apple Metal isn't available (unsupported hardware, OOM, or the daemon is down).",
    endpoints: [
      ["POST", "/v1/inference", "Run inference on Modal GPU; returns tokens + stats"],
      ["POST", "/v1/inference/stream", "Server-sent-events token stream"],
    ],
    how: "The client reports why local Metal is unavailable (no_metal_device / oom / daemon_down). The API verifies the license and routes the prompt to a deployed Modal GPU function, logging the usage.",
  },
  {
    name: "Telemetry",
    tag: "telemetry",
    purpose: "Usage events from the MCP server feed publisher reports and the monitoring view.",
    endpoints: [
      ["POST", "/v1/telemetry/events", "Batch-ingest deploy/inference/download events"],
      ["GET", "/v1/me/usage", "Your recent usage summary"],
    ],
    how: "The local server posts batched events (tokens/sec, latency, path). Publishers see aggregates per model; you see your own recent activity.",
  },
];

export default function HowItWorks() {
  return (
    <div className="container-x py-14">
      <Badge tone="accent">Documentation</Badge>
      <h1 className="mt-4 text-4xl font-bold text-white">How each service works</h1>
      <p className="mt-3 max-w-2xl text-slate-300">
        The backend is a FastAPI app exposing REST/JSON over HTTPS, deployed on Modal and backed by MongoDB Atlas,
        Cloudflare R2, and a Modal GPU inference app. Base URL:{" "}
        <a href={API_URL} className="code" target="_blank" rel="noreferrer">{API_URL}</a>
      </p>

      {/* Lifecycle */}
      <Card className="mt-10 p-6">
        <h2 className="text-lg font-semibold text-white">The end-to-end lifecycle</h2>
        <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            "Publisher uploads a GGUF model → admin approves it",
            "Consumer browses the catalog and opens a model",
            "Consumer acquires a free license",
            "MCP server binds the device and verifies the license",
            "Weights download from R2 into local secure storage",
            "Metal engine runs inference on the Apple GPU — or Modal does, as a cloud fallback",
          ].map((s, i) => (
            <li key={i} className="flex gap-3 rounded-xl border border-white/10 bg-ink-900/40 p-3">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent/20 text-xs font-bold text-accent-glow">{i + 1}</span>
              <span className="text-sm text-slate-300">{s}</span>
            </li>
          ))}
        </ol>
      </Card>

      {/* Services */}
      <div className="mt-10 space-y-6">
        {services.map((s) => (
          <Card key={s.tag} className="p-6">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-xl font-semibold text-white">{s.name}</h2>
              <Badge>{s.tag}</Badge>
            </div>
            <p className="mt-2 text-slate-300">{s.purpose}</p>

            <div className="mt-5 grid gap-6 lg:grid-cols-2">
              <div>
                <p className="label">Key endpoints</p>
                <div className="space-y-2">
                  {s.endpoints.map(([m, p, d]) => (
                    <div key={p} className="rounded-lg border border-white/10 bg-ink-900/40 p-2.5">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 py-0.5 text-[0.65rem] font-bold ${m === "GET" ? "bg-sky-500/20 text-sky-300" : "bg-accent/20 text-accent-glow"}`}>{m}</span>
                        <code className="font-mono text-xs text-slate-200">{p}</code>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{d}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="label">How to use it</p>
                <p className="text-sm leading-relaxed text-slate-300">{s.how}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Quickstart */}
      <Card className="mt-10 p-6">
        <h2 className="text-lg font-semibold text-white">Quickstart (cURL)</h2>
        <p className="mt-1 text-sm text-slate-400">Acquire a model and run a cloud-fallback inference in four calls.</p>
        <CodeBlock>{`# 1) Register (or log in) and capture the access token
TOKEN=$(curl -s ${API_URL}/v1/auth/register \\
  -H 'Content-Type: application/json' \\
  -d '{"email":"me@example.com","username":"me","password":"supersecret123"}' \\
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2) Find a model
MODEL=$(curl -s ${API_URL}/v1/models | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')

# 3) Acquire a free license
curl -s -X POST ${API_URL}/v1/models/$MODEL/acquire -H "Authorization: Bearer $TOKEN"

# 4) Run inference on the Modal GPU fallback
curl -s -X POST ${API_URL}/v1/inference -H "Authorization: Bearer $TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d "{\\"model_id\\":\\"$MODEL\\",\\"prompt\\":\\"Hello!\\",\\"reason\\":\\"no_metal_device\\"}"`}</CodeBlock>
      </Card>
    </div>
  );
}
