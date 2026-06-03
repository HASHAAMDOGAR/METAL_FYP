import Foundation

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Minimal client for a locally-running Ollama server (https://ollama.com).
///
/// Used by `InferenceMode.localInfer` to **download** a model (`/api/pull`) and
/// run **on-device inference** (`/api/generate`) — no marketplace backend or
/// cloud GPU involved.
public final class OllamaClient {
    /// Ollama's default local endpoint.
    public static let defaultBaseURL = URL(string: "http://localhost:11434")!

    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL = OllamaClient.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    /// True if an Ollama server is reachable (`GET /api/version`).
    public func isAvailable() async -> Bool {
        var req = URLRequest(url: baseURL.appendingPathComponent("/api/version"))
        req.timeoutInterval = 3
        do {
            let (_, resp) = try await session.data(for: req)
            return (resp as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    /// Names of models already pulled locally (`GET /api/tags`).
    public func localModels() async throws -> [String] {
        let req = URLRequest(url: baseURL.appendingPathComponent("/api/tags"))
        let (data, resp) = try await session.data(for: req)
        guard (resp as? HTTPURLResponse).map({ (200..<300).contains($0.statusCode) }) == true else {
            throw MetalLLMError.ollama("could not list local models")
        }
        return (try JSONDecoder().decode(OllamaTags.self, from: data)).models.map { $0.name }
    }

    /// True if `model` (e.g. "llama3.2" or "llama3.2:1b") is already downloaded.
    public func isModelLocal(_ model: String) async -> Bool {
        guard let names = try? await localModels() else { return false }
        return names.contains { $0 == model || $0 == "\(model):latest" || $0.hasPrefix("\(model):") }
    }

    /// Download a model (`POST /api/pull`), streaming progress as a 0…1 fraction.
    public func pull(model: String, onProgress: ((Double) -> Void)? = nil) async throws {
        var req = URLRequest(url: baseURL.appendingPathComponent("/api/pull"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 600
        req.httpBody = try JSONSerialization.data(withJSONObject: ["model": model, "stream": true])

        let (bytes, resp) = try await session.bytes(for: req)
        guard (resp as? HTTPURLResponse).map({ (200..<300).contains($0.statusCode) }) == true else {
            throw MetalLLMError.ollama("pull failed for '\(model)'")
        }
        for try await line in bytes.lines {
            guard let data = line.data(using: .utf8),
                  let status = try? JSONDecoder().decode(OllamaPullStatus.self, from: data) else { continue }
            if let err = status.error { throw MetalLLMError.ollama("pull error: \(err)") }
            if let total = status.total, let completed = status.completed, total > 0 {
                onProgress?(Double(completed) / Double(total))
            }
        }
    }

    /// Run a (non-streaming) completion (`POST /api/generate`).
    public func generate(model: String, prompt: String, maxTokens: Int, temperature: Double) async throws -> InferenceResult {
        var req = URLRequest(url: baseURL.appendingPathComponent("/api/generate"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 600
        let body: [String: Any] = [
            "model": model,
            "prompt": prompt,
            "stream": false,
            "options": ["num_predict": maxTokens, "temperature": temperature],
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, resp) = try await session.data(for: req)
        guard (resp as? HTTPURLResponse).map({ (200..<300).contains($0.statusCode) }) == true else {
            let msg = String(data: data, encoding: .utf8) ?? "request failed"
            throw MetalLLMError.ollama("generate failed: \(msg)")
        }
        let r = try JSONDecoder().decode(OllamaGenerateResponse.self, from: data)

        var tps = 0.0
        if let count = r.eval_count, let durNs = r.eval_duration, durNs > 0 {
            tps = (Double(count) / (Double(durNs) / 1_000_000_000)).rounded(toPlaces: 2)
        }
        return InferenceResult(
            output: r.response,
            tokensGenerated: r.eval_count ?? 0,
            tokensPerSec: tps,
            path: "local_ollama"
        )
    }
}

// MARK: - Wire types

private struct OllamaTags: Decodable {
    struct Model: Decodable { let name: String }
    let models: [Model]
}
private struct OllamaPullStatus: Decodable {
    let status: String?
    let total: Int?
    let completed: Int?
    let error: String?
}
private struct OllamaGenerateResponse: Decodable {
    let response: String
    let done: Bool?
    let eval_count: Int?
    let eval_duration: Int?
    let prompt_eval_count: Int?
}

private extension Double {
    func rounded(toPlaces places: Int) -> Double {
        let p = pow(10.0, Double(places))
        return (self * p).rounded() / p
    }
}
