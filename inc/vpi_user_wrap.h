#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"
#include <functional>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

// Cross-platform dynamic loading
#ifdef _WIN32
  #include <windows.h>
  #ifndef RTLD_DEFAULT
    #define RTLD_DEFAULT NULL
  #endif
  // Windows does not have dlerror. Provide a stub that always returns NULL.
  // This is only safe because we treat dlerror()==NULL as "no error" in
  // vpi_func_optional; since dlsym's GetProcAddress on Windows does not
  // set per-thread error state, treating any non-NULL return as success
  // is correct.
  #define dlerror() ((const char*)NULL)
#else
  #include <dlfcn.h>
#endif

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
    if (t == nullptr) {
      return nb::none();
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
  std::vector<vpiHandle> c_ref_handles;
  vpiHandle refHandle1 = nullptr;
  vpiHandle refHandle2 = nullptr;

  for (const auto &arg : ref_handles) {
    if (nb::isinstance<nb::capsule>(arg)) {
      nb::capsule cap = nb::cast<nb::capsule>(arg);
      c_ref_handles.push_back((vpiHandle) cap.data());
    } else {
      throw std::runtime_error(
          "Invalid argument type for vpiHandle conversion.");
    }
  }
  if (c_ref_handles.size() >= 2) {
    refHandle1 = c_ref_handles[0];
    refHandle2 = c_ref_handles[1];
    c_ref_handles.erase(c_ref_handles.begin(), c_ref_handles.begin() + 2);
  } else {
    vpi_printf((PLI_BYTE8*)"Error: c_ref_handles does not contain at least two elements.\n");
  }
  vpiHandle h = vpi_handle_multi(type, refHandle1, refHandle2, c_ref_handles.data());
  return convert(h);
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
                                          PLI_INT32 *index_array) {
  vpiHandle handle = convert(object);
  vpiHandle h = vpi_handle_by_multi_index(handle, num_index, index_array);
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

int vpi_control_wrap(int operation, nb::args args) {
  std::vector<void *> c_args;
  for (const auto &arg : args) {
    if (nb::isinstance<nb::capsule>(arg)) {
      nb::capsule cap = nb::cast<nb::capsule>(arg);
      c_args.push_back(cap.data());
    } else if (!arg.is_none()) {
      c_args.push_back(nullptr);
    }
  }
  return vpi_control(operation, c_args.data());
}

struct CallbackInfo {
  nb::object nb_callback;
  std::string user_data;

  CallbackInfo(nb::object cb, std::string ud)
      : nb_callback(cb), user_data(ud) {}
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

#endif /* VPI_USER_WRAP_H */