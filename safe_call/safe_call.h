#ifndef SAFE_CALL_H
#define SAFE_CALL_H

#include "core/object/object.h"
#include "core/variant/callable.h"
#include "core/error/error_macros.h"

class SafeCall : public Object {
    GDCLASS(SafeCall, Object);
    static SafeCall *singleton;

    // Thread-local variable to indicate if we are in safe mode (i.e., inside a pcall)
    static thread_local bool safe_mode;

    struct CaptureState {
        bool failed = false;
        String message;
    };
    static void _error_handler(void *p_ud, const char *p_func, const char *p_file,
                                int p_line, const char *p_err, const char *p_descr,
                                bool p_editor_notify, ErrorHandlerType p_type);

protected:
    static void _bind_methods();

public:
    static SafeCall *get_singleton() { return singleton; }
    
    // Returns true if the current thread is in safe mode (i.e., inside a pcall)
    static bool is_safe_mode() { return safe_mode; }

    Dictionary pcall(const Callable &p_callable, const Array &p_args);
    SafeCall();
    ~SafeCall();
};

#endif