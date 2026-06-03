import Foundation

/// Errors surfaced by the MetalLLM SDK.
public enum MetalLLMError: Error, CustomStringConvertible {
    /// The requested capability is not implemented yet (e.g. on-device Metal).
    case notImplemented(String)
    /// No access token — call `login()` or `setToken()` first.
    case notAuthenticated
    /// The backend returned a non-2xx response.
    case http(status: Int, code: String, message: String)
    /// The response could not be understood.
    case invalidResponse
    /// JSON decoding failed.
    case decoding(String)
    /// A local Ollama server could not be reached (not installed / not running).
    case ollamaUnavailable(String)
    /// The local Ollama server returned an error.
    case ollama(String)

    public var description: String {
        switch self {
        case .notImplemented(let m): return "Not implemented: \(m)"
        case .notAuthenticated: return "Not authenticated — call login() or setToken() first"
        case .http(let s, let c, let m): return "HTTP \(s) [\(c)]: \(m)"
        case .invalidResponse: return "Invalid response from server"
        case .decoding(let m): return "Decoding error: \(m)"
        case .ollamaUnavailable(let m): return "Ollama unavailable: \(m)"
        case .ollama(let m): return "Ollama error: \(m)"
        }
    }
}
