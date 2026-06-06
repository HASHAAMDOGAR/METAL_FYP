// matmul.mm — Native Apple Metal compute in C++/Objective-C++.
//
// Demonstrates Metal-accelerated GEMM (C = A · B), the dominant operation in
// transformer/LLM inference. The Metal shader is compiled at runtime (no Xcode
// `metal` toolchain required), dispatched on the Apple GPU, then verified and
// benchmarked against a naive CPU implementation.
//
// Build:  make           (or see Makefile)
// Run:    ./matmul [N]   (default N = 1024)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>

#include <vector>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <random>

// ---- Metal compute kernel (tiled GEMM), compiled at runtime ----------------
static NSString *const kShaderSource = @R"(
#include <metal_stdlib>
using namespace metal;

constant uint TILE = 16;

// C = A * B, all NxN, row-major. One thread per output element, with shared
// threadgroup tiles to reuse memory bandwidth.
kernel void matmul(
    device const float*  A   [[buffer(0)]],
    device const float*  B   [[buffer(1)]],
    device       float*  C   [[buffer(2)]],
    constant     uint&   N   [[buffer(3)]],
    uint2 gid  [[thread_position_in_grid]],
    uint2 lid  [[thread_position_in_threadgroup]],
    uint2 tgid [[threadgroup_position_in_grid]])
{
    threadgroup float As[TILE][TILE];
    threadgroup float Bs[TILE][TILE];

    uint row = tgid.y * TILE + lid.y;
    uint col = tgid.x * TILE + lid.x;

    float acc = 0.0f;
    uint tiles = (N + TILE - 1) / TILE;
    for (uint t = 0; t < tiles; ++t) {
        uint aCol = t * TILE + lid.x;
        uint bRow = t * TILE + lid.y;
        As[lid.y][lid.x] = (row < N && aCol < N) ? A[row * N + aCol] : 0.0f;
        Bs[lid.y][lid.x] = (bRow < N && col < N) ? B[bRow * N + col] : 0.0f;
        threadgroup_barrier(mem_flags::mem_threadgroup);

        for (uint k = 0; k < TILE; ++k)
            acc += As[lid.y][k] * Bs[k][lid.x];
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (row < N && col < N)
        C[row * N + col] = acc;
}
)";

static double now_ms() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}

static void cpu_matmul(const float *A, const float *B, float *C, uint32_t N) {
    for (uint32_t i = 0; i < N; ++i)
        for (uint32_t j = 0; j < N; ++j) {
            float s = 0.0f;
            for (uint32_t k = 0; k < N; ++k) s += A[i * N + k] * B[k * N + j];
            C[i * N + j] = s;
        }
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        const uint32_t N = (argc > 1) ? (uint32_t)atoi(argv[1]) : 1024u;
        const uint32_t TILE = 16;
        printf("Apple Metal native GEMM  —  N = %u (%.1f MFLOP per multiply)\n",
               N, 2.0 * N * N * N / 1e6);

        // --- Device & pipeline ---
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "No Metal device available.\n"); return 1; }
        printf("GPU: %s\n", device.name.UTF8String);

        NSError *err = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:kShaderSource options:nil error:&err];
        if (!lib) { fprintf(stderr, "Shader compile failed: %s\n", err.localizedDescription.UTF8String); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"matmul"];
        id<MTLComputePipelineState> pso = [device newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { fprintf(stderr, "Pipeline failed: %s\n", err.localizedDescription.UTF8String); return 1; }
        id<MTLCommandQueue> queue = [device newCommandQueue];

        // --- Host data (unified memory) ---
        const size_t count = (size_t)N * N;
        const size_t bytes = count * sizeof(float);
        std::vector<float> hA(count), hB(count), hCref(count);
        std::mt19937 rng(1234);
        std::uniform_real_distribution<float> dist(-1.f, 1.f);
        for (size_t i = 0; i < count; ++i) { hA[i] = dist(rng); hB[i] = dist(rng); }

        id<MTLBuffer> bA = [device newBufferWithBytes:hA.data() length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> bB = [device newBufferWithBytes:hB.data() length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> bC = [device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> bN = [device newBufferWithBytes:&N length:sizeof(uint32_t) options:MTLResourceStorageModeShared];

        MTLSize tg   = MTLSizeMake(TILE, TILE, 1);
        MTLSize grid = MTLSizeMake((N + TILE - 1) / TILE * TILE, (N + TILE - 1) / TILE * TILE, 1);

        auto dispatch = [&]() {
            id<MTLCommandBuffer> cb = [queue commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setBuffer:bA offset:0 atIndex:0];
            [enc setBuffer:bB offset:0 atIndex:1];
            [enc setBuffer:bC offset:0 atIndex:2];
            [enc setBuffer:bN offset:0 atIndex:3];
            [enc dispatchThreadgroups:MTLSizeMake(grid.width / TILE, grid.height / TILE, 1)
                threadsPerThreadgroup:tg];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
        };

        // --- Warmup + timed GPU runs ---
        dispatch();
        const int iters = 10;
        double t0 = now_ms();
        for (int i = 0; i < iters; ++i) dispatch();
        double gpu_ms = (now_ms() - t0) / iters;

        // --- CPU reference (single pass) ---
        double c0 = now_ms();
        cpu_matmul(hA.data(), hB.data(), hCref.data(), N);
        double cpu_ms = now_ms() - c0;

        // --- Verify ---
        const float *gpuC = (const float *)bC.contents;
        double maxErr = 0.0;
        for (size_t i = 0; i < count; ++i)
            maxErr = std::max(maxErr, (double)std::fabs(gpuC[i] - hCref[i]));

        double flop = 2.0 * (double)N * N * N;
        printf("\nGPU (Metal):  %8.2f ms/iter   %7.1f GFLOP/s\n", gpu_ms, flop / (gpu_ms / 1e3) / 1e9);
        printf("CPU (naive):  %8.2f ms         %7.1f GFLOP/s\n", cpu_ms, flop / (cpu_ms / 1e3) / 1e9);
        printf("Speedup:      %8.1fx\n", cpu_ms / gpu_ms);
        printf("Max abs error vs CPU: %.2e  %s\n", maxErr, (maxErr < 1e-2 ? "(OK)" : "(CHECK)"));
        return (maxErr < 1e-2) ? 0 : 2;
    }
}
