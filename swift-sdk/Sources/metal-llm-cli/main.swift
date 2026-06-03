import Foundation
import MetalLLM

// A small demo driving the SDK against the deployed backend.
//
//   swift run metal-llm-cli "Your prompt here"
//
// Env overrides: METALLLM_API, METALLLM_EMAIL, METALLLM_PASSWORD

func runDemo() async {
    let env = ProcessInfo.processInfo.environment
    let base = env["METALLLM_API"].flatMap(URL.init(string:)) ?? MetalLLM.defaultBaseURL
    let email = env["METALLLM_EMAIL"] ?? "admin@metal.dev"
    let password = env["METALLLM_PASSWORD"] ?? "admin12345"
    let args = CommandLine.arguments.dropFirst().joined(separator: " ")
    let prompt = args.isEmpty ? "Q: What is the capital of France?\nA:" : args

    let client = MetalLLM(baseURL: base)
    print("MetalLLM SDK demo  ->  \(base.absoluteString)")

    do {
        print("• Logging in as \(email) …")
        try await client.login(username: email, password: password)

        print("• Listing models …")
        let models = try await client.listModels()
        guard let first = models.first else { print("  (no models found)"); return }
        print("  using: \(first.name) [\(first.architecture)]  id=\(first.id)")

        // ---- managed-cloud (implemented) ----
        print("• managed-cloud inference (routes to Modal GPU) …")
        let cloudModel = client.model(id: first.id, mode: .managedCloud)
        let start = Date()
        let result = try await cloudModel.generate(prompt: prompt, maxTokens: 32)
        let secs = Int(-start.timeIntervalSinceNow)
        print("  path=\(result.path)  tokens=\(result.tokensGenerated)  tok/s=\(result.tokensPerSec)  (\(secs)s)")
        print("  output: \(result.output.trimmingCharacters(in: .whitespacesAndNewlines))")

        // ---- local-infer via Ollama (download + on-device) ----
        let ollamaTag = env["METALLLM_OLLAMA_MODEL"] ?? "qwen2.5:0.5b"
        print("• local-infer via Ollama (model: \(ollamaTag)) …")
        let localModel = client.model(id: first.id, mode: .localInfer(ollamaModel: ollamaTag))
        do {
            var lastPct = -1
            let localStart = Date()
            let local = try await localModel.generate(prompt: prompt, maxTokens: 32) { pct in
                let p = Int(pct * 100)
                if p != lastPct, p % 10 == 0 { lastPct = p; print("    downloading \(p)%") }
            }
            let lsecs = Int(-localStart.timeIntervalSinceNow)
            print("  path=\(local.path)  tokens=\(local.tokensGenerated)  tok/s=\(local.tokensPerSec)  (\(lsecs)s)")
            print("  output: \(local.output.trimmingCharacters(in: .whitespacesAndNewlines))")
        } catch {
            print("  -> \(error)")
        }

        print("✓ done")
    } catch {
        print("ERROR: \(error)")
        exit(1)
    }
}

await runDemo()
