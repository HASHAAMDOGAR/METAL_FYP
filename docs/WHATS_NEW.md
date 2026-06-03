# What's New — Capabilities

A running summary of capabilities added on top of the original backend + web app.

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

Live web app: https://hashaamdogar--metal-marketplace-web-web.modal.run/how-it-works

---

## 🔭 Still optional / pending
- **Cloudflare R2** storage (local fallback active) — swap in with an R2 token.
- **Per-API Modal services** — coded behind `DEPLOY_PER_API=1`, blocked by Modal's web-function plan limit.
- **Full macOS MCP daemon** (Swift/Metal via llama.cpp) — local inference is covered by the Ollama path in the SDK today; a custom daemon would replace Ollama later.

See **[../PROJECT_END_TO_END.md](../PROJECT_END_TO_END.md)** for the complete project report and
**[ARCHITECTURE_COMMUNICATION.md](ARCHITECTURE_COMMUNICATION.md)** for how the pieces talk to each other.
