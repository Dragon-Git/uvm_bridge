#include <pybind11/pybind11.h>
#include <pybind11/embed.h> // everything needed for embedding
#include "svdpi.h"
namespace py = pybind11;

extern "C" void body() {
    py::scoped_interpreter guard{}; // start the interpreter and keep it alive

    py::print("Hello, World!"); // use the Python API
}

int add(int i, int j) {
    return i + j;
}

PYBIND11_MODULE(example, m) {
    m.doc() = "pybind11 example plugin"; // 可选模块文档字符串

    m.def("add", &add, "A function which adds two numbers");
}