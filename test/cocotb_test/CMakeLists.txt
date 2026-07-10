cmake_minimum_required(VERSION 3.15)
project(cocotb_test LANGUAGES CXX)

find_package(Python REQUIRED COMPONENTS Interpreter Development)

if(WIN32)
    find_package(Perl REQUIRED)
endif()

find_program(VERILATOR NAMES verilator_bin.exe verilator.exe verilator_bin verilator
    PATHS $ENV{VERILATOR_ROOT}/bin
    NO_DEFAULT_PATH
)
if(NOT VERILATOR)
    find_program(VERILATOR NAMES verilator_bin.exe verilator.exe verilator_bin verilator)
endif()
if(NOT VERILATOR)
    message(FATAL_ERROR "verilator not found")
endif()
message(STATUS "Found verilator: ${VERILATOR}")

if(WIN32)
    if(NOT DEFINED ENV{VERILATOR_ROOT})
        message(FATAL_ERROR "VERILATOR_ROOT environment variable is required on Windows")
    endif()
    # Use forward slashes to avoid backslash-escaping issues in the Perl wrapper's sh_escape
    file(TO_CMAKE_PATH "$ENV{VERILATOR_ROOT}/bin/verilator" VERILATOR_SCRIPT)
    if(NOT EXISTS ${VERILATOR_SCRIPT})
        message(FATAL_ERROR "Verilator Perl script not found at ${VERILATOR_SCRIPT}")
    endif()
    set(VERILATOR_CMD ${PERL_EXECUTABLE} ${VERILATOR_SCRIPT})
    message(STATUS "Using perl to run verilator: ${VERILATOR_CMD}")
else()
    set(VERILATOR_CMD ${VERILATOR})
endif()

execute_process(
    COMMAND ${Python_EXECUTABLE} -m svuvm.config
    OUTPUT_VARIABLE SVUVM_CONFIG_OUTPUT
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE SVUVM_CONFIG_RESULT
)
if(NOT SVUVM_CONFIG_RESULT EQUAL 0)
    message(FATAL_ERROR "svuvm.config failed: ${SVUVM_CONFIG_RESULT}")
endif()

execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import svuvm, os; print(os.path.dirname(svuvm.__file__))"
    OUTPUT_VARIABLE SVUVM_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
message(STATUS "svuvm dir: ${SVUVM_DIR}")

execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import cocotb, os; print(os.path.dirname(cocotb.__file__))"
    OUTPUT_VARIABLE COCOTB_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE COCOTB_DIR_RESULT
)
if(NOT COCOTB_DIR_RESULT EQUAL 0)
    message(FATAL_ERROR "cocotb not found")
endif()
message(STATUS "cocotb dir: ${COCOTB_DIR}")

execute_process(
    COMMAND ${Python_EXECUTABLE} -m cocotb.config --lib-dir
    OUTPUT_VARIABLE COCOTB_LIB_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE COCOTB_LIB_RESULT
)
if(NOT COCOTB_LIB_RESULT EQUAL 0)
    message(FATAL_ERROR "cocotb-config --lib-dir failed")
endif()
message(STATUS "cocotb lib dir: ${COCOTB_LIB_DIR}")

execute_process(
    COMMAND ${Python_EXECUTABLE} -m cocotb.config --share
    OUTPUT_VARIABLE COCOTB_SHARE
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE COCOTB_SHARE_RESULT
)
if(NOT COCOTB_SHARE_RESULT EQUAL 0)
    message(FATAL_ERROR "cocotb-config --share failed")
endif()
message(STATUS "cocotb share: ${COCOTB_SHARE}")

set(COCOTB_VERILATOR_CPP ${COCOTB_SHARE}/lib/verilator/verilator.cpp)

get_filename_component(PROJECT_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../.. ABSOLUTE)
set(UVM_HOME ${PROJECT_ROOT}/uvm-verilator/src)
set(TEST_DIR ${CMAKE_CURRENT_SOURCE_DIR})
set(BUILD_DIR ${CMAKE_CURRENT_BINARY_DIR}/build)
set(SVUVM_PKG_SV ${SVUVM_DIR}/python_bridge_pkg.sv)

set(VERILATOR_FLAGS
    --vpi -cc --exe --build --timing
    -top top -Mdir ${BUILD_DIR}
    -Wno-lint -Wno-style -Wno-SYMRSVDWORD
    -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND
    -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN
    -Wno-ZERODLY -Wno-CASTCONST
)

set(INCLUDE_DIRS +incdir+${UVM_HOME})

set(CXX_CFLAGS
    -CFLAGS "-I${UVM_HOME}/dpi"
    -CFLAGS "-I${PROJECT_ROOT}/inc"
    -CFLAGS "-DVERILATOR"
)

set(SV_SOURCES
    ${UVM_HOME}/dpi/uvm_dpi.cc
    ${UVM_HOME}/uvm_pkg.sv
    ${SVUVM_PKG_SV}
    ${TEST_DIR}/top.sv
)

if(WIN32)
    set(DEF_FILE ${PROJECT_ROOT}/inc/svuvm.def)
    set(SVUVM_LIB ${BUILD_DIR}/_svuvm.lib)
    add_custom_command(
        OUTPUT ${SVUVM_LIB}
        COMMAND lib.exe /def:${DEF_FILE} /out:${SVUVM_LIB} /machine:x64
        DEPENDS ${DEF_FILE}
        COMMENT "Generating _svuvm.lib from svuvm.def"
    )
    set(SVUVM_LIB_DEPENDS ${SVUVM_LIB})
    get_filename_component(PYTHON_LIB_DIR ${Python_EXECUTABLE} DIRECTORY)
    set(PYTHON_LIB_DIR ${PYTHON_LIB_DIR}/libs)
    set(PYTHON_LIB ${PYTHON_LIB_DIR}/python${Python_VERSION_MAJOR}${Python_VERSION_MINOR}.lib)
    set(COCOTB_LIB ${COCOTB_LIB_DIR}/cocotbvpi_verilator.lib)
    set(LDFLAGS
        -LDFLAGS ${SVUVM_LIB}
        -LDFLAGS ${PYTHON_LIB}
        -LDFLAGS "/LIBPATH:${PYTHON_LIB_DIR}"
        -LDFLAGS "/LIBPATH:${COCOTB_LIB_DIR}"
        -LDFLAGS "cocotbvpi_verilator.lib"
        -LDFLAGS "/DELAYLOAD:_svuvm.pyd"
        -LDFLAGS "delayimp.lib"
    )
    set(VTOP_EXE ${BUILD_DIR}/Vtop.exe)
else()
    set(SVUVM_LIB_DEPENDS "")
    set(LDFLAGS
        -LDFLAGS "-Wl,-rpath,${COCOTB_LIB_DIR} -L${COCOTB_LIB_DIR} -lcocotbvpi_verilator"
    )
    string(REGEX MATCH "-LDFLAGS \"[^\"]*\"" SVUVM_LDFLAGS "${SVUVM_CONFIG_OUTPUT}")
    set(VTOP_EXE ${BUILD_DIR}/Vtop)
endif()

add_custom_target(build
    COMMAND ${CMAKE_COMMAND} -E env "VERILATOR_ROOT=$ENV{VERILATOR_ROOT}" ${VERILATOR_CMD} ${VERILATOR_FLAGS} ${INCLUDE_DIRS} ${SV_SOURCES} ${CXX_CFLAGS} ${LDFLAGS} ${COCOTB_VERILATOR_CPP}
    DEPENDS ${SVUVM_LIB_DEPENDS}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Building Vtop with verilator (cocotb)"
)

if(WIN32)
    set(RUN_ENV
        ${CMAKE_COMMAND} -E env
        "PATH=${SVUVM_DIR};${COCOTB_LIB_DIR};$ENV{PATH}"
        "PYTHONPATH=${TEST_DIR};$ENV{PYTHONPATH}"
        "PYGPI_PYTHON_BIN=${Python_EXECUTABLE}"
        "PYGPI_USERS=cocotb._init:init_package_from_simulation"
        "COCOTB_TEST_MODULES=base_test"
    )
else()
    set(RUN_ENV
        ${CMAKE_COMMAND} -E env
        "DYLD_LIBRARY_PATH=${SVUVM_DIR}:${COCOTB_LIB_DIR}:$ENV{DYLD_LIBRARY_PATH}"
        "PYTHONPATH=${TEST_DIR}:$ENV{PYTHONPATH}"
        "PYGPI_PYTHON_BIN=${Python_EXECUTABLE}"
        "PYGPI_USERS=cocotb._init:init_package_from_simulation"
        "COCOTB_TEST_MODULES=base_test"
    )
endif()

set(RUN_FLAGS
    +UVM_TESTNAME=base_test
    +UVM_NO_RELNOTES
    +UVM_OBJECTION_TRACE
)

add_custom_target(run
    COMMAND ${RUN_ENV} ${VTOP_EXE} ${RUN_FLAGS}
    DEPENDS build
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Running cocotb test"
)