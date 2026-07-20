cmake_minimum_required(VERSION 3.15...3.27)
project(svuvm LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)

if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

execute_process(
  COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT)
find_package(nanobind CONFIG REQUIRED)

add_custom_command(
  OUTPUT ${CMAKE_SOURCE_DIR}/inc/vpi_attr.h
  COMMAND "${Python_EXECUTABLE}" ${CMAKE_SOURCE_DIR}/scripts/generate_vpi_attr.py ${CMAKE_SOURCE_DIR}
  DEPENDS ${CMAKE_SOURCE_DIR}/inc/vpi_user.h ${CMAKE_SOURCE_DIR}/inc/sv_vpi_user.h ${CMAKE_SOURCE_DIR}/scripts/generate_vpi_attr.py
  COMMENT "Generating vpi_attr.h"
  VERBATIM
)

add_custom_command(
  OUTPUT ${CMAKE_SOURCE_DIR}/src/svuvm/python_bridge_pkg.sv
  COMMAND "${Python_EXECUTABLE}" ${CMAKE_SOURCE_DIR}/scripts/generate_sv_export.py ${CMAKE_SOURCE_DIR}
  DEPENDS ${CMAKE_SOURCE_DIR}/scripts/generate_sv_export.py
  COMMENT "Generating SV export declarations"
  VERBATIM
)

file(GLOB SVUVM_SOURCES "src/svuvm/*.cpp")

# On Windows, compile dpi_stub.c directly into the _svuvm module
# (as object files) so that the VPI/SV DPI stubs are statically
# linked into _svuvm.pyd. This avoids the need to link a separate
# dpi_stub library while still satisfying the linker. At runtime,
# when loaded inside a SystemVerilog simulator, the simulator's
# real VPI symbols take precedence over these stubs.
# The svuvm.def file (in inc/) controls the exported symbols so that
# only PyInit__svuvm and the SV-facing DPI exports are visible to the
# Python/SV environment, while VPI references remain private.
if(WIN32)
  enable_language(C)
  set(SVUVM_SOURCES ${SVUVM_SOURCES} inc/dpi_stub.c)
endif()

nanobind_add_module(
  _svuvm
  NOMINSIZE
  ${SVUVM_SOURCES}
)

add_custom_target(generate_vpi_attr DEPENDS ${CMAKE_SOURCE_DIR}/inc/vpi_attr.h)
add_custom_target(generate_sv_export DEPENDS ${CMAKE_SOURCE_DIR}/src/svuvm/python_bridge_pkg.sv)
add_dependencies(_svuvm generate_vpi_attr generate_sv_export)

target_include_directories(_svuvm PRIVATE inc)

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
elseif(WIN32)
  # Disable dllimport for VPI/DPI functions so that the stubs in
  # dpi_stub.c (compiled directly into _svuvm) can satisfy the
  # references without __imp_ prefix.
  target_compile_definitions(_svuvm PRIVATE PLI_DLLISPEC= DPI_DLLISPEC=)
  # Use svuvm.def to control exported symbols. This explicitly
  # declares PyInit__svuvm and the SV-facing DPI export functions
  # as exported, and ensures the resulting .pyd is properly named
  # (resolves MSB8012 TargetPath/OutputFile mismatch warnings).
  set_target_properties(_svuvm PROPERTIES
    WINDOWS_EXPORT_ALL_SYMBOLS OFF
  )
  target_link_options(_svuvm PRIVATE
    "/DEF:${CMAKE_SOURCE_DIR}/inc/svuvm.def"
  )
endif()

add_library(dpi_stub SHARED inc/dpi_stub.c)
set_target_properties(dpi_stub PROPERTIES
  POSITION_INDEPENDENT_CODE ON
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
  PREFIX ""
  C_VISIBILITY_PRESET default
)

if(WIN32)
  set_target_properties(dpi_stub PROPERTIES
    WINDOWS_EXPORT_ALL_SYMBOLS ON
    SUFFIX ".dll"
  )
  # Suppress C4273: inconsistent dll linkage warnings.
  # VPI functions are declared with __declspec(dllimport) in headers
  # but defined without decoration in dpi_stub.c. We intentionally
  # override dllimport with empty macros to avoid __imp_ prefix.
  target_compile_definitions(dpi_stub PRIVATE PLI_DLLISPEC= DPI_DLLISPEC=)
else()
  set_target_properties(dpi_stub PROPERTIES
    WINDOWS_EXPORT_ALL_SYMBOLS ON
  )
endif()

# Stub generation is skipped on Windows because MSVC multi-config
# generators place the .pyd in a Release/ subdirectory, which
# gen_stub.py does not currently handle. Stubs are nice-to-have
# for IDE autocompletion but are not required at runtime.
if(NOT WIN32)
  add_custom_command(
    OUTPUT ${CMAKE_BINARY_DIR}/_svuvm/__init__.pyi ${CMAKE_BINARY_DIR}/_svuvm/vpi.pyi
    COMMAND "${Python_EXECUTABLE}" ${CMAKE_SOURCE_DIR}/scripts/gen_stub.py -i ${CMAKE_BINARY_DIR} -m _svuvm -r -O ${CMAKE_BINARY_DIR}
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    DEPENDS _svuvm dpi_stub ${CMAKE_SOURCE_DIR}/scripts/gen_stub.py
    COMMENT "Generating Python stubs for _svuvm (recursive)"
    VERBATIM
  )

  add_custom_target(svuvm_stub ALL DEPENDS ${CMAKE_BINARY_DIR}/_svuvm/__init__.pyi)
endif()

install(TARGETS _svuvm LIBRARY DESTINATION svuvm)

if(NOT WIN32)
  install(DIRECTORY ${CMAKE_BINARY_DIR}/_svuvm
          DESTINATION svuvm
          FILES_MATCHING PATTERN "*.pyi")
endif()