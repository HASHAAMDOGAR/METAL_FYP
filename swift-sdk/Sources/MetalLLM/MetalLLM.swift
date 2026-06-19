import Foundation

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Client for the Apple Metal-Powered LLM Marketplace backend.
///
/// ```swift
/// let client = MetalLLM()                       // defaults to the deployed API
/// try await client.login(username: "admin@metal.dev", password: "admin12345")
/// let model = client.model(id: someId, mode: .managedCloud)
/// let result = try await model.generate(prompt: "Hello!")
/// print(result.output)
/// ```
public final class MetalLLM {
    /// Default base URL = the deployed FastAPI backend on Modal.
    public static let defaultBaseURL = URL(string: "https://symia-cloud--metal-marketplace-api-api.modal.run")!

    public let baseURL: URL
    /// Stable per-machine identifier sent with inference (for telemetry/binding).
    public let deviceID: String
    /// Local Ollama client used by `.localInfer`.
    public let ollama: OllamaClient

    private var accessToken: String?
    private let session: URLSession

    public init(
        baseURL: URL = MetalLLM.defaultBaseURL,
        ollamaBaseURL: URL = OllamaClient.defaultBaseURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
        self.deviceID = MetalLLM.loadDeviceID()
        self.ollama = OllamaClient(baseURL: ollamaBaseURL, session: session)
    }

    // MARK: - Auth

    /// Use an existing access token instead of logging in.
    public func setToken(_ token: String) { self.accessToken = token }

    /// Exchange credentials for a JWT access token.
    public func login(username: String, password: String) async throws {
        var req = URLRequest(url: baseURL.appendingPathComponent("/v1/auth/login"))
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = "username=\(Self.formEncode(username))&password=\(Self.formEncode(password))"
            .data(using: .utf8)
        let tokens: TokenResponse = try await send(req)
        self.accessToken = tokens.access_token
    }

    // MARK: - Catalog

    /// List approved models in the marketplace (optionally text-searched).
    public func listModels(query: String? = nil) async throws -> [ModelSummary] {
        var comps = URLComponents(
            url: baseURL.appendingPathComponent("/v1/models"),
            resolvingAgainstBaseURL: false
        )!
        if let q = query { comps.queryItems = [URLQueryItem(name: "q", value: q)] }
        var req = URLRequest(url: comps.url!)
        req.httpMethod = "GET"
        let page: ModelsPage = try await send(req)
        return page.items
    }

    /// Create a handle for a model, choosing how it should run.
    public func model(id: String, mode: InferenceMode) -> LLMModel {
        LLMModel(id: id, mode: mode, client: self)
    }

    /// Convenience for a purely-local Ollama model (no marketplace id needed).
    public func localModel(ollamaModel: String) -> LLMModel {
        LLMModel(id: "local:\(ollamaModel)", mode: .localInfer(ollamaModel: ollamaModel), client: self)
    }

    // MARK: - Internal (used by LLMModel)

    /// Idempotently ensure the user holds a (free) license for the model.
    func ensureLicense(modelId: String) async throws {
        guard accessToken != nil else { throw MetalLLMError.notAuthenticated }
        var req = URLRequest(url: baseURL.appendingPathComponent("/v1/models/\(modelId)/acquire"))
        req.httpMethod = "POST"
        _ = try? await sendRaw(req) // 201 new or 200/idempotent; safe to ignore
    }

    /// Run inference via the managed cloud backend (Modal GPU).
    func cloudInference(modelId: String, prompt: String, maxTokens: Int, temperature: Double) async throws -> InferenceResult {
        guard accessToken != nil else { throw MetalLLMError.notAuthenticated }
        var req = URLRequest(url: baseURL.appendingPathComponent("/v1/inference"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let payload: [String: Any] = [
            "model_id": modelId,
            "prompt": prompt,
            "max_tokens": maxTokens,
            "temperature": temperature,
            "reason": "no_metal_device",
            "device_id": deviceID,
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)
        let r: InferenceAPIResponse = try await send(req)
        return InferenceResult(
            output: r.output,
            tokensGenerated: r.tokens_generated,
            tokensPerSec: r.tokens_per_sec,
            path: r.path
        )
    }

    // MARK: - Networking core

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data = try await sendRaw(request)
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw MetalLLMError.decoding("\(error)") }
    }

    private func sendRaw(_ request: URLRequest) async throws -> Data {
        var req = request
        if let token = accessToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw MetalLLMError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if let env = try? JSONDecoder().decode(ErrorEnvelope.self, from: data) {
                throw MetalLLMError.http(status: http.statusCode, code: env.error.code, message: env.error.message)
            }
            throw MetalLLMError.http(status: http.statusCode, code: "error", message: "Request failed")
        }
        return data
    }

    // MARK: - Helpers

    private static func formEncode(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? s
    }

    /// Stable device id persisted under ~/.metalllm/device_id.
    private static func loadDeviceID() -> String {
        let dir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".metalllm")
        let file = dir.appendingPathComponent("device_id")
        if let data = try? Data(contentsOf: file),
           let s = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
           !s.isEmpty {
            return s
        }
        let id = "swift-sdk-" + UUID().uuidString
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? id.data(using: .utf8)?.write(to: file)
        return id
    }
}
