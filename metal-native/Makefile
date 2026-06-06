# Native Apple Metal compute — build with Command Line Tools (no full Xcode needed).
CXX      = clang++
CXXFLAGS = -std=c++17 -O2 -fobjc-arc -Wall
FRAMEWORKS = -framework Metal -framework Foundation

matmul: matmul.mm
	$(CXX) $(CXXFLAGS) matmul.mm $(FRAMEWORKS) -o matmul

run: matmul
	./matmul

clean:
	rm -f matmul

.PHONY: run clean
