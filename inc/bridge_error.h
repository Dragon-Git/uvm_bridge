#pragma once
#include <exception>
#include <new>
#include <string>
#include <utility>
#include <nanobind/nanobind.h>

namespace nb = nanobind;

struct BridgeError : std::exception {
  explicit BridgeError(std::string msg) : msg_(std::move(msg)) {}
  const char *what() const noexcept override { return msg_.c_str(); }
private:
  std::string msg_;
};
struct BridgeInvalidArgument : BridgeError { using BridgeError::BridgeError; };
struct BridgeOutOfRange      : BridgeError { using BridgeError::BridgeError; };
struct BridgeUnsupported     : BridgeError { using BridgeError::BridgeError; };

inline void register_bridge_errors(nb::module_ &m) {
  // 根先注册，子类后注册（translator 头插，后注册先匹配）。
  nb::exception<BridgeError>(m, "BridgeError");

  // nanobind 3.1 的 nb::make_tuple 无法把 PyExc_*（_object*&）cast 成
  // Python 对象（实测抛 cast_error/std::bad_cast）。这里直接用 CPython
  // 构造 (BridgeError, 内建异常) 元组；tuple 仍原样传给 PyErr_NewException，
  // 多继承语义与设计方案一致。
  nb::object bridge_error = m.attr("BridgeError");
  auto bases = [&bridge_error](PyObject *builtin) {
    PyObject *raw = PyTuple_Pack(2, bridge_error.ptr(), builtin);
    if (raw == nullptr) {
      throw std::bad_alloc();
    }
    return nb::steal<nb::object>(nb::handle(raw));
  };

  nb::exception<BridgeInvalidArgument>(
      m, "BridgeInvalidArgument", bases(PyExc_ValueError));
  nb::exception<BridgeOutOfRange>(
      m, "BridgeOutOfRange", bases(PyExc_IndexError));
  nb::exception<BridgeUnsupported>(
      m, "BridgeUnsupported", bases(PyExc_RuntimeError));
}
