#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"

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

template <typename Func> auto vpi_func_wrap(Func func) {
  using FuncPointerType = std::decay_t<Func>;
  using FuncType = std::remove_pointer_t<FuncPointerType>;

  return std::function<FuncType>([func](auto &&...args) {
    // 对每个参数进行类型转换
    auto converted_args = std::forward_as_tuple(convert(std::forward<decltype(args)>(args))...);
    auto result = func(std::forward<decltype(converted_args)>(converted_args));
    return convert<decltype(result)>(result);
  });
}

py::object vpi_register_cb_wrap(p_cb_data cb_data_p) {
  vpiHandle h = vpi_register_cb(cb_data_p);
  return convert(h);
}

PLI_INT32 vpi_remove_cb_wrap(py::object object) {
  vpiHandle handle = convert(object);
  return vpi_remove_cb(handle);
}

void vpi_get_cb_info_wrap(py::object object, p_cb_data cb_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_cb_info(handle, cb_data_p);
}

py::object vpi_register_systf_wrap(p_vpi_systf_data systf_data_p) {
  vpiHandle h = vpi_register_systf(systf_data_p);
  return convert(h);
}

void vpi_get_systf_info_wrap(py::object object, p_vpi_systf_data systf_data_p) {
  vpiHandle handle = convert(object);
  vpi_get_systf_info(handle, systf_data_p);
}

py::object vpi_handle_by_name_wrap(const std::string &name, py::object scope) {
  vpiHandle handle = convert(scope);
  vpiHandle h = vpi_handle_by_name((PLI_BYTE8 *)name.c_str(), handle);
  return convert(h);
}

py::object vpi_handle_by_index_wrap(py::object object, PLI_INT32 indx) {
  vpiHandle handle = convert(object);
  vpiHandle h = vpi_handle_by_index(handle, indx);
  return convert(h);
}

py::object vpi_handle_wrap(PLI_INT32 type, py::object refHandle) {
  vpiHandle handle = convert(refHandle);
  vpiHandle h = vpi_handle(type, handle);
  return convert(h);
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

py::object vpi_iterate_wrap(PLI_INT32 type, py::object refHandle) {
  vpiHandle handle = convert(refHandle);
  vpiHandle h = vpi_iterate(type, handle);
  return convert(h);
}

py::object vpi_scan_wrap(py::object object) {
  vpiHandle iter = convert(object);
  vpiHandle h = vpi_scan(iter);
  return convert(h);
}

PLI_INT32 vpi_get_wrap(PLI_INT32 property, py::object object) {
  vpiHandle handle = convert(object);
  return vpi_get(property, handle);
}

PLI_INT64 vpi_get64_wrap(PLI_INT32 property, py::object object) {
  vpiHandle handle = convert(object);
  return vpi_get64(property, handle);
}

PLI_BYTE8 *vpi_get_str_wrap(PLI_INT32 property, py::object object) {
  vpiHandle handle = convert(object);
  return vpi_get_str(property, handle);
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

PLI_INT32 vpi_free_object_wrap(py::object object) {
  vpiHandle handle = convert(object);
  return vpi_free_object(handle);
}

PLI_INT32 vpi_release_handle_wrap(py::object object) {
  vpiHandle handle = convert(object);
  return vpi_release_handle(handle);
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
