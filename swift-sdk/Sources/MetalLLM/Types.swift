import Foundation

/// Where a model runs its inference.
public enum InferenceMode: Sendable {
    /// Routes inference to the managed cloud backend (Modal GPU).
    case managedCloud
    /// Runs locally via a downloaded **Ollama** model (`ollamaModel` is the tag,
    /// e.g. "llama3.2", "qwen2.5:0.5b"). Downloads the model on first use.
    case localInfer(ollamaModel: String)
}

/// The result of a generation request.
public struct InferenceResult: Sendable {
    public let output: String
    public let tokensGenerated: Int
    public let tokensPerSec: Double
    /// "cloud_modal" for managed-cloud, "local_metal" once local inference lands.
    public let path: String
}

/// A model as listed in the marketplace catalog.
public struct ModelSummary: Sendable, Decodable {
    public let id: String
    public let slug: String
    public let name: String
    public let architecture: String
}

// MARK: - Internal wire types (snake_case from the API)

struct TokenResponse: Decodable { let access_token: String; let refresh_token: String }
struct ModelsPage: Decodable { let items: [ModelSummary]; let total: Int }
struct InferenceAPIResponse: Decodable {
    let output: String
    let tokens_generated: Int
    let tokens_per_sec: Double
    let path: String
}
struct ErrorEnvelope: Decodable {
    struct Body: Decodable { let code: String; let message: String }
    let error: Body
}
