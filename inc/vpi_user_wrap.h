#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"

#define GET_HANDLE(cap, handle)                                                \
  vpiHandle handle;                                                            \
  if (!cap.is_none()) {                                                        \
    py::capsule cap_ = cap;                                                        \
    handle = cap_.get_pointer<unsigned int>();                                    \
  } else {                                                                     \
    handle = nullptr;                                                          \
  }

#define RETURN_HANDLE(handle)                                                  \
  if (handle == nullptr) {                                                     \
    return py::none();                                                         \
  }                                                                            \
  return py::capsule(handle, "vpiHandle");

py::object vpi_register_cb_wrap(p_cb_data cb_data_p) {
  vpiHandle h = vpi_register_cb(cb_data_p);
  RETURN_HANDLE(h)
}

PLI_INT32 vpi_remove_cb_wrap(py::object cb_obj) {
  GET_HANDLE(cb_obj, handle)
  return vpi_remove_cb(handle);
}

void vpi_get_cb_info_wrap(py::object object, p_cb_data cb_data_p) {
  GET_HANDLE(object, handle)
  vpi_get_cb_info(handle, cb_data_p);
}

py::object vpi_register_systf_wrap(p_vpi_systf_data systf_data_p) {
  vpiHandle h = vpi_register_systf(systf_data_p);
  RETURN_HANDLE(h)
}

void vpi_get_systf_info_wrap(py::object object, p_vpi_systf_data systf_data_p) {
  GET_HANDLE(object, handle)
  vpi_get_systf_info(handle, systf_data_p);
}

py::object vpi_handle_by_name_wrap(const std::string &name, py::object scope) {
  GET_HANDLE(scope, handle)
  vpiHandle h = vpi_handle_by_name((PLI_BYTE8 *)name.c_str(), handle);
  RETURN_HANDLE(h)
}

py::object vpi_handle_by_index_wrap(py::object object, PLI_INT32 indx) {
  GET_HANDLE(object, handle)
  vpiHandle h = vpi_handle_by_index(handle, indx);
  RETURN_HANDLE(h)
}

py::object vpi_handle_wrap(PLI_INT32 type, py::object refHandle) {
  GET_HANDLE(refHandle, handle)
  vpiHandle h = vpi_handle(type, handle);
  RETURN_HANDLE(h)
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
  RETURN_HANDLE(h)
}

py::object vpi_iterate_wrap(PLI_INT32 type, py::object refHandle) {
  GET_HANDLE(refHandle, handle)
  vpiHandle h = vpi_iterate(type, handle);
  RETURN_HANDLE(h)
}

py::object vpi_scan_wrap(py::object object) {
  GET_HANDLE(object, iter)
  vpiHandle h = vpi_scan(iter);
  RETURN_HANDLE(h)
}

PLI_INT32 vpi_get_wrap(PLI_INT32 property, py::object object) {
  GET_HANDLE(object, handle)
  return vpi_get(property, handle);
}

PLI_INT64 vpi_get64_wrap(PLI_INT32 property, py::object object) {
  GET_HANDLE(object, handle)
  return vpi_get64(property, handle);
}

PLI_BYTE8 *vpi_get_str_wrap(PLI_INT32 property, py::object object) {
  GET_HANDLE(object, handle)
  return vpi_get_str(property, handle);
}

void vpi_get_delays_wrap(py::object object, p_vpi_delay delay_p) {
  GET_HANDLE(object, handle)
  vpi_get_delays(handle, delay_p);
}

void vpi_put_delays_wrap(py::object object, p_vpi_delay delay_p) {
  GET_HANDLE(object, handle)
  vpi_put_delays(handle, delay_p);
}

void vpi_get_value_wrap(py::object expr, p_vpi_value value_p) {
  GET_HANDLE(expr, handle)
  vpi_get_value(handle, value_p);
}

py::object vpi_put_value_wrap(py::object object, p_vpi_value value_p,
                              p_vpi_time time_p, PLI_INT32 flags) {
  GET_HANDLE(object, handle)
  vpiHandle h = vpi_put_value(handle, value_p, time_p, flags);
  RETURN_HANDLE(h)
}

void vpi_get_value_array_wrap(py::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 * index_p, PLI_UINT32 num) {
  GET_HANDLE(object, handle)
  vpi_get_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_put_value_array_wrap(py::object object, p_vpi_arrayvalue arrayvalue_p,
                              PLI_INT32 * index_p, PLI_UINT32 num) {
  GET_HANDLE(object, handle)
  vpi_put_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_get_time_wrap(py::object object, p_vpi_time time_p) {
  GET_HANDLE(object, handle)
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
  GET_HANDLE(object, handle)
  return vpi_free_object(handle);
}

PLI_INT32 vpi_release_handle_wrap(py::object object) {
  GET_HANDLE(object, handle)
  return vpi_release_handle(handle);
}
void *vpi_get_userdata_wrap(py::object obj) {
  GET_HANDLE(obj, handle)
  return vpi_get_userdata(handle);
}

PLI_INT32 vpi_put_userdata_wrap(py::object obj, py::object userdata) {
  GET_HANDLE(obj, handle)
  void *data = userdata.cast<void *>();
  return vpi_put_userdata(handle, data);
}

py::object vpi_handle_by_multi_index_wrap(py::object obj, PLI_INT32 num_index,
                                          PLI_INT32 *index_array) {
  GET_HANDLE(obj, handle)
  vpiHandle h = vpi_handle_by_multi_index(handle, num_index, index_array);
  RETURN_HANDLE(h)
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
