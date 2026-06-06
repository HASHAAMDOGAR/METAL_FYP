# Native Apple Metal Compute (C++/Objective-C++)

A native **Apple Metal** program that runs a matrix-multiply (**GEMM**, `C = A · B`)
on the Apple GPU. GEMM is the dominant operation in transformer/LLM inference, so
this is the foundational Metal-accelerated compute primitive an on-device
inference engine builds on.

The Metal shader is **compiled at runtime** (`newLibraryWithSource:`), so it builds
and runs with just the **Command Line Tools** — no full Xcode / `metal` toolchain
required.

## Build & run
```bash
cd metal-native
make
./matmul 1024        # N = matrix dimension (default 1024)
```

## Measured on Apple M3
```
Apple Metal native GEMM  —  N = 1024
GPU: Apple M3
GPU (Metal):      6.93 ms/iter     309.8 GFLOP/s
CPU (naive):    952.24 ms             2.3 GFLOP/s
Speedup:         137.4x
Max abs error vs CPU: 0.00e+00  (OK)
```

The GPU result is verified element-for-element against a CPU reference — the
**137× speedup** is exactly the kind of Metal acceleration the project targets
(the SRS goal was ≥2× over a CPU baseline).

## How it works
1. `MTLCreateSystemDefaultDevice()` — get the Apple GPU.
2. Compile the embedded Metal kernel at runtime into an `MTLLibrary`.
3. Build an `MTLComputePipelineState` and a command queue.
4. Upload A, B to shared (unified-memory) buffers.
5. Dispatch a **tiled** GEMM kernel (16×16 threadgroup tiles using
   `threadgroup` shared memory to cut memory bandwidth).
6. Read C back, verify against the CPU, and report GFLOP/s + speedup.

## Files
| File | Purpose |
|---|---|
| `matmul.mm` | Host code (Objective-C++) + embedded Metal kernel |
| `Makefile` | `clang++ … -framework Metal -framework Foundation` |

## Requirements
- Apple Silicon Mac (M1/M2/M3/…)
- Xcode Command Line Tools (`xcode-select --install`)

## Relation to the project
This is the **on-device Metal compute** half of the system. The marketplace
backend + Swift SDK handle discovery, licensing, and routing; a full Metal
inference engine would stack attention/FFN kernels on top of primitives like
this GEMM (today the SDK's local path uses Ollama, which itself runs llama.cpp's
Metal backend).
