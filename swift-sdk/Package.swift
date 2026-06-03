// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MetalLLM",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "MetalLLM", targets: ["MetalLLM"]),
        .executable(name: "metal-llm-cli", targets: ["MetalLLMCLI"]),
    ],
    targets: [
        .target(name: "MetalLLM"),
        .executableTarget(
            name: "MetalLLMCLI",
            dependencies: ["MetalLLM"],
            path: "Sources/metal-llm-cli"
        ),
        .testTarget(name: "MetalLLMTests", dependencies: ["MetalLLM"]),
    ]
)
