# What's New — Capabilities

A running summary of capabilities added on top of the original backend + web app.

> **Live (Modal `symia-cloud` workspace):**
> Web app — https://symia-cloud--metal-marketplace-web-web.modal.run ·
> Cloud Models — https://symia-cloud--metal-marketplace-web-web.modal.run/cloud ·
> API — https://symia-cloud--metal-marketplace-api-api.modal.run

---

## ☁️ Cloud Models — hosted catalog + in-browser chat (`/cloud`)

A new **Cloud Models** page lets users browse **hundreds of hosted models** on our managed GPU
cloud and chat with any of them instantly — no download, no setup.

- **Catalog** — every hosted model, searchable, with org · type · context length. Backend route
  `GET /v1/cloud-models`.
- **Chat** — multi-turn chat against any ready model. Backend route `POST /v1/cloud-models/chat`
  (requires a signed-in user).
- **"Ready to run" is verified, not guessed.** The upstream catalog has no reliable serverless
  flag (per-token pricing over-predicts — most priced models still reject as "non-serverless").
  So `scripts/refresh_serverless.py` **probes every text model** with a tiny call and records the
  truly-runnable IDs in `app/serverless_models.py`. The badge reflects that allowlist.
- **Reasoning models handled** — models that emit chain-of-thought (GPT-OSS, GLM, Qwen3-thinking)
  return their answer in `content` and thinking in `reasoning`; the backend surfaces something
  useful instead of a blank reply, and the UI defaults to a generous token budget.
- **White-labeled** — the upstream provider (an OpenAI-compatible service, configured via the
  `metal-backend-config` secret) is **never exposed** to users: model names, organizations, ids,
  and error messages are all sanitized so only our brand is shown.

| Mode | What happens | Path |
|---|---|---|
| Cloud Models chat | `POST /v1/cloud-models/chat` → managed cloud provider | `cloud_managed` |

---

## ♾️ No token limit

Inference no longer caps `max_tokens`. The API schema dropped its `le=4096` ceiling, the Modal GPU
function raises the context window and treats `max_tokens <= 0` as "unlimited" (generate until EOS
or the context fills), and the web UI exposes a free token input / presets (incl. ∞). Use as many
tokens as you want.

---

## 🎨 Redesigned web UI

The whole site was rebuilt for a premium, cohesive look:

- Inter typeface sitewide, layered gradient + dotted-grid background, glass-morphism cards with
  hover lift + glow, gradient buttons.
- New glassy **navbar** (animated active pill, mobile menu) and refreshed footer.
- **Homepage** hero refresh + closing CTA; **marketplace** cards get colorful gradient avatars.
- **Cloud Models** ships a full chat experience: gradient message bubbles, model avatars, typing
  indicator, suggestion chips, token presets, and live "ready" pulse indicators.

---

## 🍎 Native Swift SDK (`swift-sdk/`)

A SwiftPM package, **`MetalLLM`**, so native macOS apps run LLM inference with one
API and choose *where* it runs.

```swift
import MetalLLM

let client = MetalLLM()
try await client.login(username: "admin@metal.dev", password: "admin12345")

// Cloud GPU (Modal)
let cloud = client.model(id: modelId, mode: .managedCloud)
let a = try await cloud.generate(prompt: "Hello!")          // path: cloud_modal

// Local, on-device via Ollama (downloads on first use)
let local = client.localModel(ollamaModel: "qwen2.5:0.5b")
let b = try await local.generate(prompt: "Hello!")          // path: local_ollama
```

### Two inference modes
| Mode | What happens | Path |
|---|---|---|
| `.managedCloud` | Auto-acquires a free license, then `POST /v1/inference` → **Modal GPU** | `cloud_modal` |
| `.localInfer(ollamaModel:)` | **Downloads** the model via Ollama (`/api/pull`), then runs it **on-device** (`/api/generate`) | `local_ollama` |

### Verified (Apple Silicon M3)
- `swift build` ✅ · CLI demo runs end-to-end.
- **managed-cloud** → Modal GPU → real output (`path=cloud_modal`).
- **local-infer** → downloaded `qwen2.5:0.5b` 0→100% via the SDK, then ran on-device:
  **~136 tokens/sec** (`path=local_ollama`) — roughly **30× faster** than the cloud round-trip.

### Requirements
- macOS 13+, Swift 5.9+.
- Local mode needs Ollama: `brew install --cask ollama` then `ollama serve`.
  *(The Homebrew formula `ollama` may lack the `llama-server` runner — use the cask/app.)*

---

## 💻 Local model download + inference (Ollama)

The SDK's `.localInfer` brings **fully on-device** inference: no marketplace
backend, no cloud GPU. Ollama uses llama.cpp's **Metal** backend, so this is
genuine Apple-GPU-accelerated local inference. It implements the Ollama REST API:

1. `GET /api/version` — is Ollama running? (else `.ollamaUnavailable` with a hint)
2. `GET /api/tags` — already downloaded?
3. `POST /api/pull` — download with streamed progress (0…1)
4. `POST /api/generate` — run inference; tokens/sec from `eval_count` / `eval_duration`

---

## 🌐 Where to use each feature

| Feature | Web (browser) | Native macOS app |
|---|---|---|
| Cloud inference (Modal) | ✅ **Playground** page on the live site | ✅ `.managedCloud` |
| Local inference (Ollama) | ⚠️ only when the site runs on `localhost` (HTTPS→`http://localhost` is blocked on the deployed site) | ✅ `.localInfer` (recommended) |

- **Website now:** open `/how-it-works` (documents the SDK + both modes) and `/playground` (live cloud inference).
- **Local inference is a native capability** — use the Swift SDK in a Mac app, or run the web app locally to reach a local Ollama.

Live web app: https://symia-cloud--metal-marketplace-web-web.modal.run/how-it-works

---

## 🔭 Still optional / pending
- **Cloudflare R2** storage (local fallback active) — swap in with an R2 token.
- **Per-API Modal services** — coded behind `DEPLOY_PER_API=1`, blocked by Modal's web-function plan limit.
- **Full macOS MCP daemon** (Swift/Metal via llama.cpp) — local inference is covered by the Ollama path in the SDK today; a custom daemon would replace Ollama later.

See **[../PROJECT_END_TO_END.md](../PROJECT_END_TO_END.md)** for the complete project report and
**[ARCHITECTURE_COMMUNICATION.md](ARCHITECTURE_COMMUNICATION.md)** for how the pieces talk to each other.
