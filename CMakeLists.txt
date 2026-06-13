cmake_minimum_required(VERSION 3.15...3.27)
project(svuvm LANGUAGES C CXX)

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 查找Python开发组件
find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)

# 通过scikit-build-core自动安装的nanobind
# scikit-build-core会在隔离构建环境中安装build dependencies
# nanobind会安装在构建环境的site-packages中
if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

find_program(PYTHON_EXECUTABLE python3)

# Detect the installed nanobind package and import it into CMake
execute_process(
  COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT)
find_package(nanobind CONFIG REQUIRED)

# 代码生成：在构建前生成必要的文件
# 生成VPI属性头文件
add_custom_command(
  OUTPUT ${CMAKE_SOURCE_DIR}/inc/vpi_attr.h
  COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/generate_vpi_attr.py ${CMAKE_SOURCE_DIR}
  DEPENDS ${CMAKE_SOURCE_DIR}/inc/vpi_user.h ${CMAKE_SOURCE_DIR}/inc/sv_vpi_user.h ${CMAKE_SOURCE_DIR}/scripts/generate_vpi_attr.py
  COMMENT "Generating vpi_attr.h"
  VERBATIM
)

# 生成SV导出声明(直接修改源文件)
add_custom_command(
  OUTPUT ${CMAKE_SOURCE_DIR}/src/svuvm/python_bridge_pkg.sv
  COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/generate_sv_export.py ${CMAKE_SOURCE_DIR}
  DEPENDS ${CMAKE_SOURCE_DIR}/scripts/generate_sv_export.py
  COMMENT "Generating SV export declarations"
  VERBATIM
)

# 收集源文件
file(GLOB SVUVM_SOURCES "src/svuvm/*.cpp")

# 创建nanobind模块
nanobind_add_module(
  _svuvm
  NOMINSIZE
  ${SVUVM_SOURCES}
)

# 添加代码生成的依赖 - 使用自定义目标而非直接引用文件路径
add_custom_target(generate_vpi_attr DEPENDS ${CMAKE_SOURCE_DIR}/inc/vpi_attr.h)
add_custom_target(generate_sv_export DEPENDS ${CMAKE_SOURCE_DIR}/src/svuvm/python_bridge_pkg.sv)
add_dependencies(_svuvm generate_vpi_attr generate_sv_export)

# 添加包含目录
target_include_directories(_svuvm PRIVATE inc)

# 允许未定义符号（由模拟器在运行时提供 DPI 函数）
# 在 macOS 上：强制构建为 dylib (MH_DYLIB) 而非 bundle (MH_BUNDLE)，
#   这样同一个 .so 文件既可被 Python 导入，也可被 Verilator 链接
# 在 Linux 上：显式允许共享库中有未解析符号，并禁用链接器的 --no-undefined
if(APPLE)
  set_target_properties(_svuvm PROPERTIES
    BUNDLE FALSE
    MACOSX_RPATH TRUE
  )
  target_link_options(_svuvm PRIVATE
    "-undefined" "dynamic_lookup"
    "-Wl,-dylib"
  )
elseif(UNIX)
  target_link_options(_svuvm PRIVATE
    "-Wl,-z,lazy"
    "-Wl,-z,undefs"
  )
endif()

# 自动生成 Python stub 文件 (.pyi)
# DPI 库包含由仿真器在运行时提供的未定义符号
# 先构建提供这些符号的 dpi_stub 共享库，再通过自定义脚本预加载它来生成 stub
# 使用 -r 递归生成子模块（如 vpi）的 stub 文件
add_library(dpi_stub SHARED inc/dpi_stub.c)
set_target_properties(dpi_stub PROPERTIES
  POSITION_INDEPENDENT_CODE ON
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
  PREFIX ""
  C_VISIBILITY_PRESET default
  WINDOWS_EXPORT_ALL_SYMBOLS ON
)

add_custom_command(
  OUTPUT ${CMAKE_BINARY_DIR}/_svuvm/__init__.pyi ${CMAKE_BINARY_DIR}/_svuvm/vpi.pyi
  COMMAND ${Python_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/gen_stub.py -i ${CMAKE_BINARY_DIR} -m _svuvm -r -O ${CMAKE_BINARY_DIR}
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  DEPENDS _svuvm dpi_stub ${CMAKE_SOURCE_DIR}/scripts/gen_stub.py
  COMMENT "Generating Python stubs for _svuvm (recursive)"
  VERBATIM
)

add_custom_target(svuvm_stub ALL DEPENDS ${CMAKE_BINARY_DIR}/_svuvm/__init__.pyi)

# 安装目标
install(TARGETS _svuvm LIBRARY DESTINATION svuvm)
install(DIRECTORY ${CMAKE_BINARY_DIR}/_svuvm
        DESTINATION svuvm
        FILES_MATCHING PATTERN "*.pyi")