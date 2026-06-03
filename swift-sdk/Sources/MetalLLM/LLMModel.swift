import Foundation

/// A handle to a model, bound to an inference mode.
///
/// Created via `MetalLLM.model(id:mode:)` or `MetalLLM.localModel(ollamaModel:)`.
public struct LLMModel {
    public let id: String
    public let mode: InferenceMode
    private let client: MetalLLM

    init(id: String, mode: InferenceMode, client: MetalLLM) {
        self.id = id
        self.mode = mode
        self.client = client
    }

    /// Generate a completion for `prompt`.
    ///
    /// - `.managedCloud`: routes to the Modal GPU backend (acquires a free
    ///    license first if needed).
    /// - `.localInfer(ollamaModel:)`: runs locally via Ollama — downloads the
    ///    model on first use, then runs inference on-device. `onDownloadProgress`
    ///    reports pull progress as a 0…1 fraction.
    public func generate(
        prompt: String,
        maxTokens: Int = 128,
        temperature: Double = 0.7,
        onDownloadProgress: ((Double) -> Void)? = nil
    ) async throws -> InferenceResult {
        switch mode {
        case .managedCloud:
            try await client.ensureLicense(modelId: id)
            return try await client.cloudInference(
                modelId: id, prompt: prompt, maxTokens: maxTokens, temperature: temperature
            )

        case .localInfer(let ollamaModel):
            let ollama = client.ollama
            guard await ollama.isAvailable() else {
                throw MetalLLMError.ollamaUnavailable(
                    "no Ollama server at \(ollama.baseURL.absoluteString). "
                    + "Install from https://ollama.com and run `ollama serve`."
                )
            }
            // Download the model if it isn't present yet.
            if await ollama.isModelLocal(ollamaModel) == false {
                try await ollama.pull(model: ollamaModel, onProgress: onDownloadProgress)
            }
            return try await ollama.generate(
                model: ollamaModel, prompt: prompt, maxTokens: maxTokens, temperature: temperature
            )
        }
    }
}
