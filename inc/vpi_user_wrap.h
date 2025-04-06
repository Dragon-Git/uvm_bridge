#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"


template <typename T>
struct replace_type { using type = T; };

template <>
struct replace_type<vpiHandle> { using type = py::object; };

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
      return py::object(py::none());
    }
    return py::object(py::capsule(t, "vpiHandle"));
  } else if constexpr (std::is_same_v<T, py::object>) {
    vpiHandle handle;
    if (!t.is_none()) {
      py::capsule cap_ = t;
      handle = cap_.get_pointer<unsigned int>();
    } else {
      handle = nullptr;
    }
    return handle;
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
void vpi_get_cb_info_wrap(py::object object, p_cb_data cb_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_cb_info(handle, cb_data_p);
}
void vpi_get_systf_info_wrap(py::object object, p_vpi_systf_data systf_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_systf_info(handle, systf_data_p);
}
py::object vpi_handle_multi_wrap(int type, py::args ref_handles) {
  std::vector<vpiHandle> c_ref_handles;
  vpiHandle refHandle1;
  vpiHandle refHandle2;

  for (const auto &arg : ref_handles) {
    if (py::isinstance<py::capsule>(arg)) {
      c_ref_handles.push_back(reinterpret_cast<vpiHandle>(
          arg.cast<py::capsule>().get_pointer<vpiHandle>()));
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
    refHandle1 = nullptr;
    refHandle2 = nullptr;
    vpi_printf((
        PLI_BYTE8
            *)"Error: c_ref_handles does not contain at least two elements.\n");
  }
  vpiHandle h =
      vpi_handle_multi(type, refHandle1, refHandle2, c_ref_handles.data());
  return convert(h);
}

void vpi_get_delays_wrap(py::object object, p_vpi_delay delay_p) {
  vpiHandle handle = convert(object);
  vpi_get_delays(handle, delay_p);
}

void vpi_put_delays_wrap(py::object object, p_vpi_delay delay_p) {
  vpiHandle handle = convert(object);
  vpi_put_delays(handle, delay_p);
}

void vpi_get_value_wrap(py::object object, p_vpi_value value_p) {
  vpiHandle handle = convert(object);
  vpi_get_value(handle, value_p);
}

py::object vpi_put_value_wrap(py::object object, p_vpi_value value_p,
                              p_vpi_time time_p, PLI_INT32 flags) {
  vpiHandle handle = convert(object);
  vpiHandle h = vpi_put_value(handle, value_p, time_p, flags);
  return convert(h);
}

void vpi_get_value_array_wrap(py::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  vpi_get_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_put_value_array_wrap(py::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  vpi_put_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_get_time_wrap(py::object object, p_vpi_time time_p) {
  vpiHandle handle = convert(object);
  vpi_get_time(handle, time_p);
}

PLI_INT32 vpi_compare_objects_wrap(py::args ref_handles) {
  std::vector<vpiHandle> c_ref_handles;
  for (const auto &arg : ref_handles) {
    if (py::isinstance<py::capsule>(arg)) {
      c_ref_handles.push_back(reinterpret_cast<vpiHandle>(
          arg.cast<py::capsule>().get_pointer<vpiHandle>()));
    } else {
      throw std::runtime_error(
          "Invalid argument type for vpiHandle conversion.");
    }
  }
  if (c_ref_handles.size() != 2) {
    vpi_printf((PLI_BYTE8 *)"Error: objects must contain two elements.\n");
  }
  return vpi_compare_objects(c_ref_handles[0], c_ref_handles[1]);
}

void *vpi_get_userdata_wrap(py::object object) {
  vpiHandle handle = convert(object);
  return vpi_get_userdata(handle);
}

PLI_INT32 vpi_put_userdata_wrap(py::object object, py::object userdata) {
  vpiHandle handle = convert(object);
  void *data = userdata.cast<void *>();
  return vpi_put_userdata(handle, data);
}

py::object vpi_handle_by_multi_index_wrap(py::object object, PLI_INT32 num_index,
                                          PLI_INT32 *index_array) {
  vpiHandle handle = convert(object);
  vpiHandle h = vpi_handle_by_multi_index(handle, num_index, index_array);
  return convert(h);
}

int vpi_mcd_printf_wrap(unsigned int mcd, py::str format, py::args args,
                        py::kwargs kwargs) {
  std::string formatted = format.format(*args, **kwargs);
  int result = vpi_mcd_printf(mcd, (char *)"%s", formatted.c_str());
  return result;
}

int vpi_printf_wrap(py::str format, py::args args, py::kwargs kwargs) {
  std::string formatted = format.format(*args, **kwargs);
  int result = vpi_printf((char *)"%s", formatted.c_str());
  return result;
}

int vpi_control_wrap(int operation, py::args args) {
  std::vector<void *> c_args;
  for (const auto &arg : args) {
    c_args.push_back(arg.cast<void *>());
  }
  return vpi_control(operation, c_args.data());
}

struct CallbackInfo {
  py::function py_callback;
  std::string user_data;

  CallbackInfo(py::function cb, std::string ud)
      : py_callback(cb), user_data(ud) {}
};

static PLI_INT32 vpi_callback_wrap(p_cb_data cb_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(cb_data->user_data);
  py::gil_scoped_acquire gil;

  try {
    py::object py_cb_data = py::cast(cb_data);
    py::object py_result = callback_info->py_callback(cb_data);
    PLI_INT32 result = py_result.cast<PLI_INT32>();
    return result;
  } catch (const py::error_already_set &e) {
    std::cerr << "Exception in python callback: " << e.what() << std::endl;
    return 0;
  }
}

static PLI_INT32 systf_callback_wrap(PLI_BYTE8 *user_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(user_data);
  py::gil_scoped_acquire gil;

  try {
    py::object py_result = callback_info->py_callback();
    PLI_INT32 result = py_result.cast<PLI_INT32>();
    return result;
  } catch (const py::error_already_set &e) {
    std::cerr << "Exception in python callback: " << e.what() << std::endl;
    return 0;
  }
}

#endif /* VPI_USER_WRAP_H */
