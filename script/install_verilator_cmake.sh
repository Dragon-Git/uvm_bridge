#! /bin/bash

# VERILATOR_ROOT="$PWD/verilator"

# Clone repo only if it doesn't exist
if [ ! -d /home/runner/work/verilator ]; then
    cd /home/runner/work/
    git clone https://github.com/verilator/verilator.git
fi

mkdir -p /home/runner/work/verilator/build
cd /home/runner/work/verilator/build

# Debug
cmake -G Ninja .. -DCMAKE_BUILD_TYPE=Release \
-DCMAKE_CXX_STANDARD=17 \
-DCFG_CXXFLAGS_STD="-std=gnu++17" \
-DCFG_CXXFLAGS_STD_NEWEST="-std=gnu++17" \
-DCFG_CXXFLAGS_COROUTINES="-std=gnu++20" \
-DCFG_CXXFLAGS_PCH_I="-include" \
-DCFG_CXXFLAGS_NO_UNUSED="-faligned-new -fcf-protection=none -Wno-bool-operation -Wno-subobject-linkage -Wno-constant-logical-operand -Wno-non-pod-varargs -Wno-parentheses-equality -Wno-shadow -Wno-sign-compare -Wno-tautological-bitwise-compare -Wno-tautological-compare -Wno-uninitialized -Wno-unused-but-set-parameter -Wno-unused-but-set-variable -Wno-unused-parameter -Wno-unused-variable" \
-DCFG_CXXFLAGS_WEXTRA="-Wextra -Wfloat-conversion -Wthread-safety" \

cmake --build . --config Release
cmake --install .
