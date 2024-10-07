#! /bin/bash

# VERILATOR_ROOT="$PWD/verilator"

# Clone repo only if it doesn't exist
if [ ! -d /home/runner/work/verilator ]; then
    cd /home/runner/work/
    git clone https://github.com/verilator/verilator.git
fi

cd /home/runner/work/verilator

# Returns non-zero if no .o files exist
find -name '*.o' | grep -q .

# If .o files don't exist, do autoconf and do make
if [ $? -ne 0 ]; then
    # git checkout v5.028
    autoconf
    ./configure
    make -j `nproc`
else
    echo "Verilator already built, skipping compile/install steps"
fi
make install

