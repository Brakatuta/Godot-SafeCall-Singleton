#include "safe_call.h"
#include "core/object/class_db.h"

SafeCall *SafeCall::singleton = nullptr;

// Initialisierung der Thread-lokalen Variable
thread_local bool SafeCall::safe_mode = false;

void SafeCall::_bind_methods() {
    ClassDB::bind_method(D_METHOD("pcall", "callable", "args"), &SafeCall::pcall);
}

SafeCall::SafeCall() { singleton = this; }
SafeCall::~SafeCall() { singleton = nullptr; }

void SafeCall::_error_handler(void *p_ud, const char *p_func, const char *p_file,
                               int p_line, const char *p_err, const char *p_descr,
                               bool p_editor_notify, ErrorHandlerType p_type) {
    CaptureState *state = (CaptureState *)p_ud;

    // 1. Safe catch of potentially null pointers for error and description
    const char *safe_err = (p_err != nullptr) ? p_err : "Unknown error";
    const char *safe_descr = (p_descr != nullptr) ? p_descr : "";
    
    // 2. Choose the most appropriate message for the log and dictionary
    const char *log_msg = (safe_descr[0] != '\0') ? safe_descr : safe_err;

    // 3. Now absolutely safe against segfaults
    printf("[SafeCall] error_handler fired: %s\n", log_msg); 

    if (p_type == ERR_HANDLER_ERROR || p_type == ERR_HANDLER_SCRIPT) {
        state->failed = true;
        state->message = String(log_msg);
    }
}

Dictionary SafeCall::pcall(const Callable &p_callable, const Array &p_args) {
    Dictionary result;

    if (!p_callable.is_valid()) {
        result["ok"] = false;
        result["error"] = "Invalid callable.";
        result["result"] = Variant();
        return result;
    }

    CaptureState state;
    ErrorHandlerList handler;
    handler.errfunc = &SafeCall::_error_handler;
    handler.userdata = &state;
    add_error_handler(&handler);

    Variant ret;
    Callable::CallError ce;
    Vector<const Variant *> argptrs;
    for (int i = 0; i < p_args.size(); i++) argptrs.push_back(&p_args[i]);

    safe_mode = true;

    p_callable.callp(argptrs.ptrw(), argptrs.size(), ret, ce);

    safe_mode = false;

    remove_error_handler(&handler);

    if (ce.error != Callable::CallError::CALL_OK) {
        result["ok"] = false;
        result["error"] = "Call error: " + Variant::get_call_error_text(
            p_callable.get_object(),
            p_callable.get_method(),
            argptrs.ptrw(),
            argptrs.size(),
            ce
        );
        result["result"] = Variant();
        return result;
    }

    if (state.failed) {
        result["ok"] = false;
        result["error"] = state.message;
        result["result"] = Variant();
        return result;
    }

    result["ok"] = true;
    result["error"] = "";
    result["result"] = ret;
    return result;
}