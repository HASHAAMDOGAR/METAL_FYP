#if canImport(XCTest)
import XCTest
@testable import MetalLLM

final class MetalLLMTests: XCTestCase {
    /// local-infer points at Ollama; with no Ollama server it must report
    /// `.ollamaUnavailable` (and never silently succeed).
    func testLocalInferRequiresOllama() async {
        // Point at a port where nothing is listening.
        let client = MetalLLM(ollamaBaseURL: URL(string: "http://127.0.0.1:1")!)
        let model = client.model(id: "any", mode: .localInfer(ollamaModel: "qwen2.5:0.5b"))
        do {
            _ = try await model.generate(prompt: "hi")
            XCTFail("expected ollamaUnavailable to be thrown")
        } catch let error as MetalLLMError {
            guard case .ollamaUnavailable = error else {
                return XCTFail("wrong error: \(error)")
            }
        } catch {
            XCTFail("unexpected error type: \(error)")
        }
    }

    /// managed-cloud without auth must require a login first.
    func testManagedCloudRequiresAuth() async {
        let client = MetalLLM()
        let model = client.model(id: "any", mode: .managedCloud)
        do {
            _ = try await model.generate(prompt: "hi")
            XCTFail("expected notAuthenticated")
        } catch let error as MetalLLMError {
            guard case .notAuthenticated = error else {
                return XCTFail("wrong error: \(error)")
            }
        } catch {
            XCTFail("unexpected error type: \(error)")
        }
    }

    func testDeviceIDIsStable() {
        let a = MetalLLM().deviceID
        let b = MetalLLM().deviceID
        XCTAssertEqual(a, b, "device id should persist across instances")
        XCTAssertTrue(a.hasPrefix("swift-sdk-"))
    }
}

#endif
