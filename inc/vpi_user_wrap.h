#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"
#include <dlfcn.h>
#include <functional>
#include <stdexcept>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;

template <typename T>
struct replace_type { using type = T; };

template <>
struct replace_type<vpiHandle> { using type = nb::object; };

template <>
struct replace_type<char*> { using type = const char*; };

// 函数特征萃取
template <typename Func>
struct func_traits;

template <typename R, typename... Args>
struct func_traits<R (*)(Args...)> {
    using return_type = typename replace_type<R>::type;
    using raw_args = std::tuple<Args...>;
    using adapted_args = std::tuple<typename replace_type<Args>::type...>;
};

template <typename T> auto convert(T t) {
  if constexpr (std::is_same_v<T, vpiHandle>) {
    // replace_type<vpiHandle> is specialized to nb::object
    // (see top of this file), so the Python-facing return
    // type is always nb::object. Returning nb::none() here
    // would give the auto return type a conflicting
    // deduction (nb::none vs nb::object) and GCC refuses to
    // compile under nanobind 3.0.0 (it tolerated this in
    // 2.4.x because nb::none had a more relaxed conversion
    // path to nb::object). Wrap into nb::object so both
    // branches agree on the deduced type.
    if (t == nullptr) {
      return nb::object(nb::none());
    }
    return nb::object(nb::capsule((void *)t, [](void *) noexcept {}));
  } else if constexpr (std::is_same_v<T, nb::object>) {
    vpiHandle handle;
    if (!t.is_none()) {
      nb::capsule cap = nb::cast<nb::capsule>(t);
      return (vpiHandle) cap.data();
    } else {
      handle = nullptr;
    }
    return handle;
  } else if constexpr (std::is_same_v<T, const char*>) {
    return const_cast<char*>(t);
  } else {
    return t;
  }
}

template <typename Ret, typename... Args>
struct wrap_func_type {
  using type = std::function<Ret(Args...)>;
};

// 定义包装函数类型，展开 tuple 中的元素作为参数类型
template <typename Ret, typename Tuple, std::size_t... Is>
auto make_wrap_func_type(std::index_sequence<Is...>) {
  return typename wrap_func_type<Ret, std::tuple_element_t<Is, Tuple>...>::type{};
}

template <typename Func> auto vpi_func_wrap(Func func) {
  using FuncPointerType = std::decay_t<Func>;
  using FuncType = std::remove_pointer_t<FuncPointerType>;
  using traits = func_traits<FuncPointerType>;
  using ReturnType = typename traits::return_type;
  using AdaptedArgs = typename traits::adapted_args;

  auto wrapFuncType = make_wrap_func_type<ReturnType, AdaptedArgs>(std::make_index_sequence<std::tuple_size_v<AdaptedArgs>>{});
  return decltype(wrapFuncType)([func](auto&&... args) {
      auto converted_args = std::make_tuple(convert(std::forward<decltype(args)>(args))...);
      auto result = std::apply(func, converted_args);
      return convert<decltype(result)>(result);
  });
}

// 运行时检测指定的 VPI 函数是否存在。若存在则返回经过 vpi_func_wrap
// 包装后的可调用对象；否则返回一个调用时抛出 runtime_error 的占位函数。
// 这样既统一了参数/返回值类型转换，也避免在绑定点写大段重复的 if/else。
template <typename Func>
auto vpi_func_optional(const char *name, Func fallback_func) {
  using FuncPointerType = std::decay_t<Func>;
  using FuncType = std::remove_pointer_t<FuncPointerType>;
  using traits = func_traits<FuncPointerType>;
  using ReturnType = typename traits::return_type;
  using AdaptedArgs = typename traits::adapted_args;

  dlerror();
  void *sym = dlsym(RTLD_DEFAULT, name);
  const char *err = dlerror();
  auto *raw_ptr = (err == nullptr && sym != nullptr)
                      ? reinterpret_cast<FuncPointerType>(sym)
                      : nullptr;

  auto wrapFuncType = make_wrap_func_type<ReturnType, AdaptedArgs>(
      std::make_index_sequence<std::tuple_size_v<AdaptedArgs>>{});

  if (raw_ptr != nullptr) {
    return decltype(wrapFuncType)([raw_ptr](auto &&...args) {
      auto converted_args = std::make_tuple(
          convert(std::forward<decltype(args)>(args))...);
      auto result = std::apply(raw_ptr, converted_args);
      return convert<decltype(result)>(result);
    });
  }
  return decltype(wrapFuncType)(
      [name, fallback_func](auto &&...args) -> ReturnType {
        if (fallback_func != nullptr) {
          return convert(std::apply(
              fallback_func,
              std::make_tuple(convert(std::forward<decltype(args)>(args))...)));
        }
        std::string msg = std::string(name) + " not supported by this simulator";
        throw std::runtime_error(msg);
      });
}
void vpi_get_cb_info_wrap(nb::object object, p_cb_data cb_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_cb_info(handle, cb_data_p);
}
void vpi_get_systf_info_wrap(nb::object object, p_vpi_systf_data systf_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_systf_info(handle, systf_data_p);
}
nb::object vpi_handle_multi_wrap(int type, nb::args ref_handles) {
  // IEEE 1800 declares vpi_handle_multi as
  //   vpiHandle vpi_handle_multi(PLI_INT32 type, vpiHandle ref1,
  //                              vpiHandle ref2, ...);
  // with "two or more" reference handles (the only relationship in common
  // use is vpiInterModPath, which takes exactly two ports). A C variadic
  // call cannot forward a runtime-sized nb::args directly, and the previous
  // code passed `vector.data()` as ONE vararg -- so a third handle was read
  // by the simulator as the vector's backing-array address, not as a handle.
  // Dispatch by fixed arity instead, and reject <2 handles up front rather
  // than calling through with null handles after only printing a message.
  const size_t n = ref_handles.size();
  if (n < 2) {
    throw std::invalid_argument(
        "vpi_handle_multi needs at least two reference handles");
  }
  const auto h = [&](size_t i) -> vpiHandle {
    nb::object arg = ref_handles[i];
    return convert(arg);
  };

  if (n == 2)
    return convert(vpi_handle_multi(type, h(0), h(1)));
  if (n == 3)
    return convert(vpi_handle_multi(type, h(0), h(1), h(2)));
  if (n == 4)
    return convert(vpi_handle_multi(type, h(0), h(1), h(2), h(3)));
  if (n == 5)
    return convert(vpi_handle_multi(type, h(0), h(1), h(2), h(3), h(4)));
  if (n == 6)
    return convert(vpi_handle_multi(type, h(0), h(1), h(2), h(3), h(4), h(5)));

  throw std::invalid_argument(
      "vpi_handle_multi supports at most six reference handles");
}

void vpi_get_delays_wrap(nb::object object, p_vpi_delay delay_p) {
  vpiHandle handle = convert(object);
  vpi_get_delays(handle, delay_p);
}

void vpi_put_delays_wrap(nb::object object, p_vpi_delay delay_p) {
  vpiHandle handle = convert(object);
  vpi_put_delays(handle, delay_p);
}

void vpi_get_value_wrap(nb::object object, p_vpi_value value_p) {
  vpiHandle handle = convert(object);
  vpi_get_value(handle, value_p);
}

nb::object vpi_put_value_wrap(nb::object object, p_vpi_value value_p,
                              p_vpi_time time_p, PLI_INT32 flags) {
  // IEEE 1800-2023 38.35: vpiInertialDelay / vpiTransportDelay /
  // vpiPureTransportDelay require a non-NULL time_p whose type is
  // vpiSimTime. vpiNoDelay ignores time_p (NULL is legal), and
  // vpiForceFlag / vpiReleaseFlag do not require one either. These delay
  // constants are mutually exclusive enum values (1..6), not bit flags,
  // so they must be compared by equality rather than with a bitmask test.
  if (flags == vpiInertialDelay || flags == vpiTransportDelay ||
      flags == vpiPureTransportDelay) {
    if (time_p == nullptr) {
      throw std::invalid_argument(
          "vpi_put_value: delay flags require a non-null time_p");
    }
    if (time_p->type != vpiSimTime) {
      throw std::invalid_argument(
          "vpi_put_value: delay time_p must have type vpiSimTime");
    }
  }
  vpiHandle handle = convert(object);
  vpiHandle h = vpi_put_value(handle, value_p, time_p, flags);
  return convert(h);
}

void vpi_get_value_array_wrap(nb::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  vpi_get_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_put_value_array_wrap(nb::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  vpi_put_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_get_time_wrap(nb::object object, p_vpi_time time_p) {
  vpiHandle handle = convert(object);
  vpi_get_time(handle, time_p);
}

void *vpi_get_userdata_wrap(nb::object object) {
  vpiHandle handle = convert(object);
  return vpi_get_userdata(handle);
}

PLI_INT32 vpi_put_userdata_wrap(nb::object object, nb::object userdata) {
  vpiHandle handle = convert(object);
  void *data = nullptr;
  if (!userdata.is_none() && nb::isinstance<nb::capsule>(userdata)) {
    nb::capsule cap = nb::cast<nb::capsule>(userdata);
    data = cap.data();
  }
  return vpi_put_userdata(handle, data);
}

nb::object vpi_handle_by_multi_index_wrap(nb::object object, PLI_INT32 num_index,
                                          const std::vector<PLI_INT32> &index_array) {
  vpiHandle handle = convert(object);
  // The IEEE signature takes a bare PLI_INT32*, which nanobind cannot build
  // from a Python list. Accept a list of indices instead and hand its backing
  // array to VPI; vector.h is already included above. Derive the count from
  // the list length so callers cannot pass a mismatched num_index that would
  // make the simulator read past the buffer.
  (void)num_index;
  PLI_INT32 count = static_cast<PLI_INT32>(index_array.size());
  vpiHandle h = vpi_handle_by_multi_index(
      handle, count, const_cast<PLI_INT32 *>(index_array.data()));
  return convert(h);
}

int vpi_mcd_printf_wrap(unsigned int mcd, const std::string &format) {
  int result = vpi_mcd_printf(mcd, (char *)"%s", format.c_str());
  return result;
}

int vpi_printf_wrap(const std::string &format) {
  int result = vpi_printf((char *)"%s", format.c_str());
  return result;
}

// vpi_control() is C-variadic: the number and types of its trailing arguments
// depend on the operation (IEEE 1800-2023 38.4 / 39.5). A C++ function cannot
// forward nb::args straight into a variadic call, so we must dispatch on the
// operation and issue a fixed-arity call with the exact types the simulator's
// va_arg sequence expects:
//   * vpiStop / vpiFinish           -> int arg
//   * vpiSetInteractiveScope        -> void *handle (a vpiScope)
//   * 620..622 (assert Disable/Enable/Reset) -> void *handle
//   * 623..625 (assert Kill/EnableStep/DisableStep)
//                                   -> void *handle, void *time_p
//   * 624 (EnableStep) additionally -> int step
//   * 633..638 (assert action controls) -> void *handle
//   * 627..632 / 639..644 / 647..648 (system ops) -> no arguments
// Passing a pointer-to-array (as an earlier version did) made the simulator
// read the array address as the first handle and garbage for later arguments.
static void *vpi_control_handle_arg(const nb::object &o) {
  if (o.is_none())
    return nullptr;
  if (nb::isinstance<nb::capsule>(o))
    return nb::cast<nb::capsule>(o).data();
  // VpiTime / VpiValue objects are exposed as nanobind classes; recover the
  // underlying C struct address so it can serve as a time_p / object handle.
  if (nb::isinstance<s_vpi_time>(o))
    return static_cast<void *>(&nb::cast<s_vpi_time &>(o));
  if (nb::isinstance<s_vpi_value>(o))
    return static_cast<void *>(&nb::cast<s_vpi_value &>(o));
  return nullptr;
}

int vpi_control_wrap(int operation, nb::args args) {
  const size_t n = args.size();
  const auto at = [&](size_t i) -> nb::object {
    return i < n ? args[i] : nb::object(nb::none());
  };

  // Assertion system-wide operations take no trailing argument at all.
  if ((operation >= 627 && operation <= 630) || operation == 632 ||
      (operation >= 639 && operation <= 644) || operation == 647 ||
      operation == 648)
    return vpi_control(operation);

  // vpiStop / vpiFinish take an integer "diagnostic level".
  if (operation == 66 /* vpiStop */ || operation == 67 /* vpiFinish */) {
    int arg = 0;
    if (!at(0).is_none()) {
      try {
        arg = nb::cast<int>(at(0));
      } catch (const std::exception &) {
        arg = 0;
      }
    }
    return vpi_control(operation, arg);
  }

  // vpiSetInteractiveScope takes a single scope handle.
  if (operation == 69 /* vpiSetInteractiveScope */)
    return vpi_control(operation, vpi_control_handle_arg(at(0)));

  // Per-assertion controls (IEEE 39.5). 620..622 need only the assertion
  // handle; 623 (Kill) and 625 (DisableStep) also take a start time; 624
  // (EnableStep) takes the start time plus the step constant.
  if (operation >= 620 && operation <= 625) {
    void *handle = vpi_control_handle_arg(at(0));
    void *time_p = vpi_control_handle_arg(at(1));
    if (operation == 624 /* vpiAssertionEnableStep */) {
      int step = 0;
      if (!at(2).is_none()) {
        try {
          step = nb::cast<int>(at(2));
        } catch (const std::exception &) {
          step = 0;
        }
      }
      return vpi_control(operation, handle, time_p, step);
    }
    if (operation == 623 /* Kill */ || operation == 625 /* DisableStep */)
      return vpi_control(operation, handle, time_p);
    return vpi_control(operation, handle);
  }

  // Per-assertion pass/fail/vacuous action controls (633..638) take just the
  // assertion handle.
  if (operation >= 633 && operation <= 638)
    return vpi_control(operation, vpi_control_handle_arg(at(0)));

  // Unknown / unruntime-supported operation: forward with no trailing args so
  // the simulator can emit its standard "operation not supported" diagnostic.
  return vpi_control(operation);
}

struct CallbackInfo {
  nb::object nb_callback;
  // IEEE 1800 36: s_vpi_systf_data exposes three independent callbacks, all
  // with the signature PLI_INT32 (*)(PLI_BYTE8*). compiletf validates
  // arguments at compile time and sizetf reports the width of a sized system
  // function; both are optional, so they default to None. The constructor
  // signature is intentionally unchanged so existing CallbackInfo(cb, ud)
  // call sites keep working.
  nb::object nb_compiletf;
  nb::object nb_sizetf;
  std::string user_data;
  // Owns a NUL-terminated string whose c_str() is handed to a C struct field
  // (e.g. s_vpi_systf_data.tfname). Lives exactly as long as the CallbackInfo
  // that the simulator holds through the systf/callback user_data pointer.
  std::string owned_str;

  CallbackInfo(nb::object cb, std::string ud)
      : nb_callback(cb), nb_compiletf(nb::none()), nb_sizetf(nb::none()),
        user_data(ud) {}
};

static PLI_INT32 vpi_callback_wrap(p_cb_data cb_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(cb_data->user_data);
  nb::gil_scoped_acquire gil;

  try {
    nb::object nb_result = callback_info->nb_callback(cb_data);
    if (nb_result.is_none()) {
      return 0;
    }
    return nb::cast<PLI_INT32>(nb_result);
  } catch (const nb::python_error &e) {
    std::cerr << "Exception in python callback: " << e.what() << std::endl;
    return 0;
  }
}

static PLI_INT32 systf_callback_wrap(PLI_BYTE8 *user_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(user_data);
  nb::gil_scoped_acquire gil;

  try {
    nb::object nb_result = callback_info->nb_callback();
    if (nb_result.is_none()) {
      return 0;
    }
    return nb::cast<PLI_INT32>(nb_result);
  } catch (const nb::python_error &e) {
    std::cerr << "Exception in python callback: " << e.what() << std::endl;
    return 0;
  }
}

// Shared dispatcher for the two newly bound systf callbacks. Both follow the
// same IEEE 1800 signature and calling convention as calltf: no arguments,
// None -> 0, int -> that value, Python exception -> diagnostic + 0.
static PLI_INT32 invoke_systf_python(const nb::object &callback,
                                    const char *kind) {
  nb::gil_scoped_acquire gil;
  try {
    nb::object nb_result = callback();
    if (nb_result.is_none()) {
      return 0;
    }
    return nb::cast<PLI_INT32>(nb_result);
  } catch (const nb::python_error &e) {
    std::cerr << "Exception in python " << kind << " callback: "
              << e.what() << std::endl;
    return 0;
  }
}

static PLI_INT32 systf_compiletf_wrap(PLI_BYTE8 *user_data) {
  auto *callback_info = reinterpret_cast<CallbackInfo *>(user_data);
  if (callback_info == nullptr || callback_info->nb_compiletf.is_none()) {
    return 0;
  }
  return invoke_systf_python(callback_info->nb_compiletf, "compiletf");
}

static PLI_INT32 systf_sizetf_wrap(PLI_BYTE8 *user_data) {
  auto *callback_info = reinterpret_cast<CallbackInfo *>(user_data);
  if (callback_info == nullptr || callback_info->nb_sizetf.is_none()) {
    return 0;
  }
  return invoke_systf_python(callback_info->nb_sizetf, "sizetf");
}

#endif /* VPI_USER_WRAP_H */