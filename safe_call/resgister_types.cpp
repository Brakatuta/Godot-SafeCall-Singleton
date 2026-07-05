#include "register_types.h"
#include "safe_call.h"
#include "core/object/class_db.h"
#include "core/config/engine.h"

static SafeCall *safe_call_singleton = nullptr;

void initialize_safe_call_module(ModuleInitializationLevel p_level) {
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) return;
    GDREGISTER_CLASS(SafeCall);
    safe_call_singleton = memnew(SafeCall);
    Engine::get_singleton()->add_singleton(Engine::Singleton("SafeCall", SafeCall::get_singleton()));
}

void uninitialize_safe_call_module(ModuleInitializationLevel p_level) {
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) return;
    memdelete(safe_call_singleton);
}