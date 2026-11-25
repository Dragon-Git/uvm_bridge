#ifndef VPI_USER_WRAP_H
#define VPI_USER_WRAP_H

#include "sv_vpi_user.h"
#include "vpi_user.h"
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <typeinfo>  // std::bad_cast: nanobind's cast_error derives from it
#include <unordered_map>
#include <utility>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;

// P0#2: CallbackInfo is completed much further down this header. Declaring it
// here lets the single LifetimeRegistry own maps keyed by / holding pointers
// to it without splitting this header-only core into a second header.
struct CallbackInfo;

// The three legacy registry accessors are kept as deprecated symbols. They
// proxy the singleton's maps; declaring them here is what grants the friend
// access used by those proxies below.
inline std::unordered_map<vpiHandle, nb::object> &userdata_keepalive_registry();
inline std::unordered_map<CallbackInfo *, std::weak_ptr<CallbackInfo>> &
callback_raw_map();
inline std::unordered_map<vpiHandle, std::shared_ptr<CallbackInfo>> &
callback_registry();

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
// Defined after the CallbackInfo ownership helpers: besides filling the C
// struct, these wrappers attach a shared_ptr capsule to the destination
// Python object so its user_data getter never reads a freed CallbackInfo.
inline void vpi_get_cb_info_wrap(nb::object object, nb::object cb_data_obj);
inline void vpi_get_systf_info_wrap(nb::object object,
                                    nb::object systf_data_obj);
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
  // vpiForceFlag / vpiReleaseFlag / vpiCancelEvent do not require one.
  // vpiReturnEvent (0x1000) is a *bit mask* that may be OR'ed with a delay
  // constant (38.34); strip it before deciding whether a time_p is required.
  // Otherwise a delayed write with vpiReturnEvent and NULL time_p would pass
  // validation and let the simulator dereference a null pointer.
  const PLI_INT32 delay_flags = flags & ~vpiReturnEvent;
  if (delay_flags == vpiInertialDelay || delay_flags == vpiTransportDelay ||
      delay_flags == vpiPureTransportDelay) {
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

// Guard vpi_get/put_value_array against writing `num` elements into an
// undersized heap buffer (IEEE 1800-2023 38.14: the tool writes exactly `num`
// elements into the caller's array). Bridge-created VpiArrayValue objects
// record their allocation length on the Python object as `_buf_len`. We read
// that attribute from the very Python object we were handed -- never from an
// arbitrary raw pointer -- so a foreign object, a default-constructed one, or
// one whose length is unknown (set_* installed an external capsule) simply
// skips validation. This is a safety check, not an API change: a legal `num`
// is forwarded unchanged.
inline void check_arrayvalue_num(const nb::object &arrayvalue_obj,
                                 PLI_UINT32 num, const char *api_name) {
  nb::object len_obj;
  try {
    len_obj = arrayvalue_obj.attr("_buf_len");
  } catch (const std::exception &) {
    return;  // no recorded length on this object; nothing we can validate
  }
  if (!len_obj.is_valid() || len_obj.is_none()) {
    return;
  }
  long long capacity = 0;
  try {
    capacity = nb::cast<long long>(len_obj);
  } catch (const std::exception &) {
    return;
  }
  if (capacity < 0) {
    return;
  }
  if (static_cast<unsigned long long>(num) >
      static_cast<unsigned long long>(capacity)) {
    throw std::out_of_range(std::string(api_name) +
                            ": num exceeds VpiArrayValue buffer length");
  }
}

void vpi_get_value_array_wrap(nb::object object, nb::object arrayvalue_obj,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  p_vpi_arrayvalue arrayvalue_p =
      &nb::cast<s_vpi_arrayvalue &>(arrayvalue_obj);
  check_arrayvalue_num(arrayvalue_obj, num, "vpi_get_value_array");
  vpi_get_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_put_value_array_wrap(nb::object object, nb::object arrayvalue_obj,
                              PLI_INT32 *index_p, PLI_UINT32 num) {
  vpiHandle handle = convert(object);
  p_vpi_arrayvalue arrayvalue_p =
      &nb::cast<s_vpi_arrayvalue &>(arrayvalue_obj);
  check_arrayvalue_num(arrayvalue_obj, num, "vpi_put_value_array");
  vpi_put_value_array(handle, arrayvalue_p, index_p, num);
}

void vpi_get_time_wrap(nb::object object, p_vpi_time time_p) {
  // IEEE 1800 38.25 allows a NULL object (global simulation time). convert()
  // maps nb::none() to a NULL vpiHandle, so None is forwarded unchanged.
  vpiHandle handle = convert(object);
  vpi_get_time(handle, time_p);
}

void *vpi_get_userdata_wrap(nb::object object) {
  vpiHandle handle = convert(object);
  return vpi_get_userdata(handle);
}

// ---------------------------------------------------------------------------
// P0#2: the single owner of the three lifetime-tracking relations that used
// to be three independent function-local statics:
//   * userdata_   : vpiHandle -> keep-alive nb::object (capsule)
//   * registered_ : vpiHandle -> shared_ptr<CallbackInfo> (registered cb)
//   * raw_        : raw user_data pointer -> weak_ptr<CallbackInfo>
// Keeping them behind one singleton puts all insertion/erase invariants in
// one place. The instance is heap-allocated and NEVER deleted: destroying
// these maps during C++ static teardown would destroy nb::object values
// without the GIL, which may already be gone at process exit.
// ---------------------------------------------------------------------------
class LifetimeRegistry {
 public:
  static LifetimeRegistry &instance() noexcept;

  // A capsule is stored (overwriting releases the old one); None or any
  // non-capsule object clears the entry, matching the old wrap exactly.
  void put_userdata(vpiHandle h, nb::object cap);
  // Precondition: caller holds the GIL (erase may destroy an nb::object).
  void forget_userdata(vpiHandle h) noexcept;

  // These four need a complete CallbackInfo; their bodies are defined right
  // after the struct later in this header.
  std::shared_ptr<CallbackInfo> make(nb::object cb, std::string ud,
                                     nb::object time, nb::object value);
  std::shared_ptr<CallbackInfo> from_raw(void *ud) noexcept;
  void register_cb(vpiHandle h, std::shared_ptr<CallbackInfo> sp);
  void release_cb(vpiHandle h) noexcept;

 private:
  LifetimeRegistry() = default;

  std::unordered_map<vpiHandle, nb::object> userdata_;
  std::unordered_map<vpiHandle, std::shared_ptr<CallbackInfo>> registered_;
  std::unordered_map<CallbackInfo *, std::weak_ptr<CallbackInfo>> raw_;

  friend std::unordered_map<vpiHandle, nb::object> &userdata_keepalive_registry();
  friend std::unordered_map<CallbackInfo *, std::weak_ptr<CallbackInfo>> &
  callback_raw_map();
  friend std::unordered_map<vpiHandle, std::shared_ptr<CallbackInfo>> &
  callback_registry();
};

inline LifetimeRegistry &LifetimeRegistry::instance() noexcept {
  static auto *p = new LifetimeRegistry();
  return *p;
}

inline void LifetimeRegistry::put_userdata(vpiHandle h, nb::object cap) {
  if (h == nullptr) {
    return;
  }
  if (!cap.is_none() && nb::isinstance<nb::capsule>(cap)) {
    userdata_[h] = std::move(cap);  // overwriting releases the old capsule
  } else {
    userdata_.erase(h);
  }
}

inline void LifetimeRegistry::forget_userdata(vpiHandle h) noexcept {
  if (h == nullptr) {
    return;
  }
  userdata_.erase(h);
}

// ---------------------------------------------------------------------------
// Bug #6: keep the Python capsule that backs a vpi_put_userdata() payload
// alive for as long as the simulator may still hold the raw void*.
//
// IEEE 1800 36.1: vpi_put_userdata stores the pointer only; it does not copy
// the memory and does not acquire a reference to the Python object. Dropping
// the last Python reference to the capsule (whose deleter frees the buffer)
// before the handle is released therefore leaves a dangling pointer in the
// simulator. The registry below holds a strong nb::object reference, keyed by
// handle, until the handle is released or the payload is replaced/cleared.
// ---------------------------------------------------------------------------
// Deprecated compatibility symbol: the storage now lives in the singleton.
// Kept for source compatibility with any out-of-tree caller (svuvm.cpp never
// calls it directly).
[[deprecated("use LifetimeRegistry::instance() instead")]]
inline std::unordered_map<vpiHandle, nb::object> &userdata_keepalive_registry() {
  return LifetimeRegistry::instance().userdata_;
}

PLI_INT32 vpi_put_userdata_wrap(nb::object object, nb::object userdata) {
  vpiHandle handle = convert(object);
  void *data = nullptr;
  if (!userdata.is_none() && nb::isinstance<nb::capsule>(userdata)) {
    nb::capsule cap = nb::cast<nb::capsule>(userdata);
    data = cap.data();
  }
  PLI_INT32 rc = vpi_put_userdata(handle, data);

  // Only a handle can carry userdata, so there is nothing to keep alive for a
  // NULL handle. Every registry mutation here is safe: installing a capsule
  // can only extend a buffer's lifetime, and clearing/replacing happens only
  // after the simulator has been told about the new pointer. Keeping the
  // entry even when the simulator reports failure is deliberate and
  // safety-first: a stale keep-alive is a small leak, never a use-after-free.
  if (handle != nullptr) {
    // The capsule check / erase-on-None is inside put_userdata so the exact
    // old semantics (including "keep the entry even if rc failed") hold.
    LifetimeRegistry::instance().put_userdata(handle, userdata);
  }
  return rc;
}

// Drop the keep-alive for a handle when it is freed/released. Otherwise a
// recycled handle could inherit a capsule belonging to a previous object.
inline void forget_userdata_keepalive(vpiHandle handle) noexcept {
  LifetimeRegistry::instance().forget_userdata(handle);
}

PLI_INT32 vpi_release_handle_wrap(nb::object object) {
  vpiHandle handle = convert(object);
  PLI_INT32 rc = vpi_release_handle(handle);
  // Symmetry with vpi_put_userdata_wrap: a failed release means the
  // simulator still holds the raw userdata pointer, so keep the capsule
  // alive. Only a successful release ends the keepalive window.
  if (rc == 1) {
    forget_userdata_keepalive(handle);
  }
  return rc;
}

PLI_INT32 vpi_free_object_wrap(nb::object object) {
  vpiHandle handle = convert(object);
  PLI_INT32 rc = vpi_free_object(handle);
  // Same reasoning as vpi_release_handle_wrap: drop the keepalive only when
  // the simulator confirmed the object was freed.
  if (rc == 1) {
    forget_userdata_keepalive(handle);
  }
  return rc;
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
//   * 645..646 (assert Lock/Unlock) -> void *handle
//   * 627..630 / 632 / 639..644 / 647..648 (system ops)
//                                   -> void *handle (scope; NULL = all)
// IEEE 1800-2023 39.5.1 requires a second handle argument even for the
// system-wide operations: a vpiHandle for a scope, where NULL means the
// control applies to all assertions regardless of scope.
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

  // Assertion system-wide operations (IEEE 1800-2023 39.5.1) take a second
  // handle argument: a vpiHandle for a scope. A NULL handle (Python None, or
  // no argument at all) means the control applies to all assertions
  // regardless of scope; a real scope handle is forwarded unchanged.
  if ((operation >= 627 && operation <= 630) || operation == 632 ||
      (operation >= 639 && operation <= 644) || operation == 647 ||
      operation == 648)
    return vpi_control(operation, vpi_control_handle_arg(at(0)));

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

  // IEEE 1800-2023 38.4: vpiReset shall be passed three additional integer
  // arguments -- stop_value, reset_value, diagnostics_value. Omitting them
  // made the simulator's va_arg sequence read stack garbage. Missing or
  // non-integer arguments default to 0, matching the 66/67 branches above.
  if (operation == 68 /* vpiReset */) {
    const auto int_arg = [&](size_t i) -> int {
      int val = 0;
      if (!at(i).is_none()) {
        try {
          val = nb::cast<int>(at(i));
        } catch (const std::exception &) {
          val = 0;
        }
      }
      return val;
    };
    return vpi_control(operation, int_arg(0), int_arg(1), int_arg(2));
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

  // vpiAssertionLock / vpiAssertionUnlock (645/646, IEEE 1800-2023 39.5.2)
  // each take one assertion handle. They used to fall through to the bare
  // vpi_control(operation) call and had that handle silently discarded.
  if (operation == 645 /* vpiAssertionLock */ ||
      operation == 646 /* vpiAssertionUnlock */)
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
  // IEEE 1800 36.1: vpi_register_cb copies s_cb_data but keeps the raw
  // time/value pointers until vpi_remove_cb. keep_alive on the Python CbData
  // wrapper only protects them while that wrapper is alive; after registration
  // the simulator is the real user. Pin the two objects on this shared
  // CallbackInfo so the registration registry keeps them alive for exactly
  // that window. None for systf data (no time/value there) and for callers
  // that do not supply them. Defaulted so all existing call sites are intact.
  nb::object nb_time = nb::none();
  nb::object nb_value = nb::none();
  std::string user_data;
  // Owns a NUL-terminated string whose c_str() is handed to a C struct field
  // (e.g. s_vpi_systf_data.tfname). Lives exactly as long as the CallbackInfo
  // that the simulator holds through the systf/callback user_data pointer.
  std::string owned_str;

  CallbackInfo(nb::object cb, std::string ud)
      : nb_callback(cb), nb_compiletf(nb::none()), nb_sizetf(nb::none()),
        user_data(ud) {}
};

// --- LifetimeRegistry methods that need a complete CallbackInfo -----------
inline std::shared_ptr<CallbackInfo>
LifetimeRegistry::make(nb::object cb, std::string ud, nb::object time,
                       nb::object value) {
  auto sp = std::make_shared<CallbackInfo>(std::move(cb), std::move(ud));
  sp->nb_time = std::move(time);
  sp->nb_value = std::move(value);
  raw_[sp.get()] = sp;  // implicit weak_ptr from shared_ptr
  return sp;
}

inline std::shared_ptr<CallbackInfo>
LifetimeRegistry::from_raw(void *ud) noexcept {
  if (ud == nullptr) {
    return nullptr;
  }
  auto it = raw_.find(static_cast<CallbackInfo *>(ud));
  if (it == raw_.end()) {
    return nullptr;
  }
  auto sp = it->second.lock();
  if (!sp) {
    raw_.erase(it);  // prune the dead control block; no owner references it
  }
  return sp;
}

inline void LifetimeRegistry::register_cb(vpiHandle h,
                                          std::shared_ptr<CallbackInfo> sp) {
  registered_[h] = std::move(sp);
}

inline void LifetimeRegistry::release_cb(vpiHandle h) noexcept {
  // Precondition: caller holds the GIL (may destroy nb::object members).
  registered_.erase(h);
}

// ---------------------------------------------------------------------------
// P0#3: the single C-boundary exception guard.
//
// Every callback below is entered from simulator C code. Letting a C++
// exception escape one of those extern "C" callbacks calls std::terminate and
// core-dumps the simulator, so all of them funnel through safe_invoke. It owns
// the GIL, applies the existing None -> 0 convention and collects the three
// former catch blocks into one implementation.
// ---------------------------------------------------------------------------

// Opt-in strict mode. The function-local static is initialised lazily, so a
// normal (non-failing) callback never calls getenv: it only reads one bool.
inline bool strict_callback_errors() noexcept {
  static const bool value = []() noexcept {
    const char *env = std::getenv("UVM_BRIDGE_STRICT_CALLBACKS");
    return env != nullptr && env[0] == '1' && env[1] == '\0';
  }();
  return value;
}

// vpi_printf / vpi_control are declared by vpi_user.h at the top of this
// header. Strict mode deliberately still returns 0 across the C boundary
// (non-zero would pollute systf results / task disable status); vpiStop makes
// the whole simulation fail so "passed but never executed" cannot stay green.
inline void report_strict_callback(const char *label,
                                   const char *detail) noexcept {
  vpi_printf((char *)"ERROR [uvm_bridge] strict callback failure in %s: %s\n",
             const_cast<char *>(label), const_cast<char *>(detail));
  vpi_control(vpiStop, 1);
}

template <class Fn, class... Args>
PLI_INT32 safe_invoke(Fn &&fn, const char *label, Args &&...args) noexcept {
  nb::gil_scoped_acquire gil;
  try {
    if constexpr (std::is_void_v<std::invoke_result_t<Fn, Args...>>) {
      // py_func's DPI body only calls the Python function and discards its
      // result; keep that exact behaviour (void -> status 0).
      std::invoke(std::forward<Fn>(fn), std::forward<Args>(args)...);
      return 0;
    } else {
      nb::object nb_result =
          std::invoke(std::forward<Fn>(fn), std::forward<Args>(args)...);
      if (nb_result.is_none()) {
        return 0;
      }
      return nb::cast<PLI_INT32>(nb_result);
    }
  } catch (nb::python_error &e) {
    // PyErr_Print semantics: keep the full Python traceback. e.what() would
    // only repeat the message and lose the traceback, so do not print it.
    e.discard_as_unraisable(label);
    if (strict_callback_errors()) {
      report_strict_callback(label, "python exception (see traceback above)");
    }
    return 0;
  } catch (const std::bad_cast &e) {
    std::cerr << "Invalid python " << label << " callback return type: "
              << e.what() << std::endl;
    if (strict_callback_errors()) {
      // Fixed stack buffer: no std::string allocation inside a noexcept body.
      char detail[1024];
      std::snprintf(detail, sizeof(detail),
                    "Invalid python %s callback return type: %s", label,
                    e.what());
      report_strict_callback(label, detail);
    }
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "Exception in python " << label << " callback: " << e.what()
              << std::endl;
    if (strict_callback_errors()) {
      char detail[1024];
      std::snprintf(detail, sizeof(detail),
                    "Exception in python %s callback: %s", label, e.what());
      report_strict_callback(label, detail);
    }
    return 0;
  }
}

static PLI_INT32 vpi_callback_wrap(p_cb_data cb_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(cb_data->user_data);
  // gil_scoped_acquire and all catch logic live inside safe_invoke now.
  return safe_invoke(
      [callback_info](p_cb_data data) { return callback_info->nb_callback(data); },
      "vpi_callback", cb_data);
}

static PLI_INT32 systf_callback_wrap(PLI_BYTE8 *user_data) {
  auto callback_info = reinterpret_cast<CallbackInfo *>(user_data);
  return safe_invoke([callback_info]() { return callback_info->nb_callback(); },
                     "systf");
}

// Shared dispatcher for the two newly bound systf callbacks. Both follow the
// same IEEE 1800 signature and calling convention as calltf: no arguments,
// None -> 0, int -> that value, Python exception -> diagnostic + 0.
static PLI_INT32 invoke_systf_python(const nb::object &callback,
                                    const char *kind) {
  return safe_invoke([&callback]() { return callback(); }, kind);
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

// ---------------------------------------------------------------------------
// Bug #5: shared ownership of CallbackInfo.
//
// IEEE 1800 36.1: vpi_register_cb / vpi_register_systf copy the s_cb_data /
// s_vpi_systf_data structure but keep the *raw* user_data pointer. The
// simulator uses that pointer for the whole registration window
// (callback: until vpi_remove_cb succeeds; systf: until the simulation ends,
// because IEEE defines no systf unregister call). Deleting a CallbackInfo
// while that window is open is a use-after-free, so it must never happen.
//
// Ownership is therefore shared between:
//   * the Python CbData / VpiSystfData object, through an nb::capsule stored
//     as an attribute (owns a copy of the shared_ptr); and
//   * the `registered` map below, keyed by the VPI handle returned from a
//     successful register call, released on a successful vpi_remove_cb.
//
// `raw_map` only holds weak_ptrs: it is a lookup table from the raw
// user_data pointer back to shared ownership, never an owner itself.
// ---------------------------------------------------------------------------
// Deprecated compatibility symbols: the storage now lives in the singleton.
// svuvm.cpp does not call either of them directly.
[[deprecated("use LifetimeRegistry::instance() instead")]]
inline std::unordered_map<CallbackInfo *, std::weak_ptr<CallbackInfo>> &
callback_raw_map() {
  return LifetimeRegistry::instance().raw_;
}

[[deprecated("use LifetimeRegistry::instance() instead")]]
inline std::unordered_map<vpiHandle, std::shared_ptr<CallbackInfo>> &
callback_registry() {
  return LifetimeRegistry::instance().registered_;
}

// Create a CallbackInfo under shared ownership and make it discoverable by
// its raw user_data pointer. Every former `new CallbackInfo` site uses this.
// `time` / `value` are the Python objects behind cb_data->time / ->value: they
// must outlive the registration window even if the Python CbData wrapper is
// collected right after vpi_register_cb (IEEE 36.1). The registry holds the
// returned shared_ptr until vpi_remove_cb succeeds; when that copy and the
// wrapper's capsule are both gone, the objects are released together with
// the simulator's use of the pointers. Systf callers pass None for both.
inline std::shared_ptr<CallbackInfo> make_callback_info(nb::object cb,
                                                        std::string ud,
                                                        nb::object time,
                                                        nb::object value) {
  return LifetimeRegistry::instance().make(std::move(cb), std::move(ud),
                                           std::move(time), std::move(value));
}

// Backwards-compatible form for the many callers with no time/value objects.
inline std::shared_ptr<CallbackInfo> make_callback_info(nb::object cb,
                                                        std::string ud) {
  return make_callback_info(std::move(cb), std::move(ud), nb::none(),
                            nb::none());
}

// Recover shared ownership from the raw pointer the simulator handed back.
// An empty result means either a NULL pointer, an object we never created,
// or one whose last shared owner is already gone -- never dereference it.
inline std::shared_ptr<CallbackInfo>
callback_info_from_raw(void *user_data) noexcept {
  // NULL handling and dead-weak_ptr pruning are inside from_raw().
  return LifetimeRegistry::instance().from_raw(user_data);
}

// Build the capsule stored on the Python CbData / VpiSystfData object. Its
// deleter destroys exactly one shared_ptr copy; the CallbackInfo itself dies
// only when the last owner (capsule or registered map) goes away, which by
// construction cannot happen while the simulator still uses the pointer.
inline nb::capsule
make_callback_info_owner(const std::shared_ptr<CallbackInfo> &sp) {
  return nb::capsule(new std::shared_ptr<CallbackInfo>(sp), [](void *p) noexcept {
    delete static_cast<std::shared_ptr<CallbackInfo> *>(p);
  });
}

// Dedicated vpi_register_cb / vpi_register_systf wrappers: after a successful
// registration, move a shared_ptr copy into `registered` so the callback stays
// alive even if the Python wrapper object is garbage-collected first.
inline nb::object vpi_register_cb_wrap(p_cb_data cb_data_p) {
  vpiHandle handle = vpi_register_cb(cb_data_p);
  if (handle != nullptr && cb_data_p != nullptr) {
    auto sp = callback_info_from_raw(cb_data_p->user_data);
    if (sp) {
      LifetimeRegistry::instance().register_cb(handle, std::move(sp));
    }
  }
  return convert(handle);
}

inline nb::object vpi_register_systf_wrap(p_vpi_systf_data systf_data_p) {
  vpiHandle handle = vpi_register_systf(systf_data_p);
  if (handle != nullptr && systf_data_p != nullptr) {
    auto sp = callback_info_from_raw(systf_data_p->user_data);
    if (sp) {
      LifetimeRegistry::instance().register_cb(handle, std::move(sp));
    }
  }
  return convert(handle);
}

// Only a successful removal ends the simulator's use of the user_data
// pointer (IEEE: vpi_remove_cb returns 1 on success). Releasing one shared
// owner here is safe: if the Python object is still alive its capsule keeps
// the CallbackInfo alive; if not, the simulator has just stopped using it.
inline PLI_INT32 vpi_remove_cb_wrap(nb::object cb_obj) {
  vpiHandle handle = convert(cb_obj);
  PLI_INT32 rc = vpi_remove_cb(handle);
  if (rc == 1 && handle != nullptr) {
    LifetimeRegistry::instance().release_cb(handle);
  }
  return rc;
}

// The destination of vpi_get_cb_info / vpi_get_systf_info receives a raw
// user_data pointer from the simulator. When it points at one of our
// CallbackInfo objects, give the destination its own shared_ptr copy so the
// user_data getter stays safe even if the original owner dies and the
// callback is removed afterwards.
inline void vpi_get_cb_info_wrap(nb::object object, nb::object cb_data_obj) {
  vpiHandle handle = convert(object);
  p_cb_data cb_data_p = &nb::cast<s_cb_data &>(cb_data_obj);
  vpi_get_cb_info(handle, cb_data_p);
  auto sp = callback_info_from_raw(cb_data_p->user_data);
  if (sp) {
    cb_data_obj.attr("_vpi_callback_info_owner") = make_callback_info_owner(sp);
  }
}

inline void vpi_get_systf_info_wrap(nb::object object,
                                    nb::object systf_data_obj) {
  vpiHandle handle = convert(object);
  p_vpi_systf_data systf_data_p =
      &nb::cast<s_vpi_systf_data &>(systf_data_obj);
  vpi_get_systf_info(handle, systf_data_p);
  auto sp = callback_info_from_raw(systf_data_p->user_data);
  if (sp) {
    systf_data_obj.attr("_vpi_callback_info_owner") =
        make_callback_info_owner(sp);
  }
}

#endif /* VPI_USER_WRAP_H */