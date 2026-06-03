# MetalLLM — Swift SDK

A native Swift SDK for the **Apple Metal-Powered LLM Marketplace**. A macOS app can
run LLM inference two ways behind one API: through the deployed **managed-cloud**
backend (Modal GPU), or **locally** by downloading and running a model via
[**Ollama**](https://ollama.com).

```swift
import MetalLLM

let client = MetalLLM()                                   // → deployed backend
try await client.login(username: "admin@metal.dev", password: "admin12345")

let models = try await client.listModels()
let model = client.model(id: models[0].id, mode: .managedCloud)

let result = try await model.generate(prompt: "Hello, who are you?")
print(result.output, result.tokensPerSec, result.path)    // … "cloud_modal"
```

## Inference modes

| Mode | Behavior | Status |
|---|---|---|
| `.managedCloud` | Routes inference to the managed cloud backend (Modal GPU). Auto-acquires a free license first. | ✅ implemented |
| `.localInfer(ollamaModel:)` | **Downloads** the model with Ollama (`/api/pull`) on first use, then runs **on-device** inference (`/api/generate`). | ✅ implemented |

```swift
// Local, on-device via Ollama (downloads on first run, then runs locally)
let local = client.localModel(ollamaModel: "qwen2.5:0.5b")
let result = try await local.generate(prompt: "Capital of Japan?") { pct in
    print("downloading \(Int(pct * 100))%")
}
print(result.path)   // "local_ollama"
```

## What it does under the hood

**managed-cloud**
1. `login` → JWT access token.
2. `generate` → idempotently `POST /v1/models/{id}/acquire` (free license).
3. `POST /v1/inference` with `reason="no_metal_device"` → Modal GPU → tokens + stats.

**local-infer (Ollama)**
1. Checks the local Ollama server (`GET /api/version`); if absent, throws `.ollamaUnavailable`.
2. If the model isn't downloaded (`GET /api/tags`), pulls it (`POST /api/pull`, streamed progress).
3. Runs inference (`POST /api/generate`) and returns tokens/sec from `eval_count`/`eval_duration`.

The cloud path consumes the same live backend the web app uses; the local path
needs only a running Ollama — no marketplace backend, no cloud GPU.

## API surface
- `MetalLLM(baseURL:)` — defaults to the deployed backend URL.
- `login(username:password:)`, `setToken(_:)`
- `listModels(query:)` → `[ModelSummary]`
- `model(id:mode:)` → `LLMModel`
- `LLMModel.generate(prompt:maxTokens:temperature:)` → `InferenceResult`
- Errors via `MetalLLMError` (`.notImplemented`, `.notAuthenticated`, `.http`, …)

## Build, test, run
```bash
cd swift-sdk
swift build
swift test                       # requires full Xcode (XCTest); guarded otherwise
swift run metal-llm-cli "Q: capital of Japan?\nA:"
```
Env overrides for the CLI: `METALLLM_API`, `METALLLM_EMAIL`, `METALLLM_PASSWORD`.

## Use it in an app (Swift Package Manager)
Add this folder as a local package, or point at the repo:
```swift
.package(url: "https://github.com/HASHAAMDOGAR/METAL_FYP.git", branch: "main")
// then depend on the "MetalLLM" product
```

## Verified (Apple Silicon M3)
- Builds with Swift 6.3 / Command Line Tools.
- CLI runs end-to-end: **managed-cloud** returns real Modal-GPU output
  (`path=cloud_modal`); **local-infer** downloads `qwen2.5:0.5b` via Ollama
  (0→100%) and runs on-device (`path=local_ollama`, ~136 tok/s).

## Requirements
- macOS 13+
- Swift 5.9+ toolchain (Xcode for `swift test`)
- For `.localInfer`: **Ollama** running locally (`ollama serve`). Install the
  official build from https://ollama.com (the Homebrew *formula* may lack the
  `llama-server` runner — use the cask/app: `brew install --cask ollama`).
