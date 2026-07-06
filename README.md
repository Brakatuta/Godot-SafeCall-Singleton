# 🚀 Godot SafeCall

**Godot SafeCall** is a custom C++ module and GDScript Virtual Machine patch for the Godot Engine. It brings Lua-style protected calls (`pcall`) to GDScript.

Normally, if GDScript encounters a hard error, such as calling a method on a `null` instance or a previously freed object, the engine throws an error. In exported release builds, these errors can often result in an immediate segmentation fault and an abrupt crash.

With **SafeCall**, you can wrap risky function calls in a protective layer. If a critical error occurs inside the `pcall`, the engine gracefully catches it, aborts the function execution cleanly, and returns an error dictionary instead of crashing your game.

---

## 🌟 Features

- **Lua-like `pcall` in GDScript**: Safely execute risky functions without risking a hard crash.
- **Release-build safe**: Patches the GDScript VM to retain critical bounds checks and null checks at runtime, even in optimized release templates.
- **Zero overhead outside of `pcall`**: The injected safety checks only run when `SafeCall::is_safe_mode()` is active. Normal engine execution remains unaffected and retains full release performance.
- **Detailed error catching**: Returns a structured dictionary containing success status, error messages, and the function's return value.

---

## 📦 Installation

To use Godot SafeCall, you need to compile the Godot Engine from source.

### 1. Add the module

Clone or copy the SafeCall module files into the `modules/` directory of your Godot Engine source code.

```text
godot/
└── modules/
    └── safe_call/
        ├── config.py
        ├── pcall_patch.py
        ├── register_types.h
        ├── resgister_types.cpp
        ├── safe_call.cpp
        ├── safe_call.h
        └── SCsub
```

### 2. Patch the GDScript VM

Because Godot strips internal safety checks in release builds (`#ifdef DEBUG_ENABLED`), you must run the included Python patcher to inject conditional runtime checks into the GDScript Virtual Machine.

Run the following command from the root of your Godot source directory:

```bash
python3 modules/safe_call/pcall_patch.py --add modules/gdscript/gdscript_vm.cpp
```

> ℹ️ Note: The patcher is fully conditional. It injects code that evaluates at runtime whether a protected call is active.

### 3. Compile Godot

Compile the engine and your export templates as usual using SCons.

```bash
# 🪟 Example for Windows Editor
scons platform=windows target=editor

# 🪟 Example for Windows Release Template
scons platform=windows target=template_release
```

---

## 🛠️ Usage

Once compiled, `SafeCall` becomes available as a global singleton in GDScript. You can pass any `Callable` and an `Array` of arguments to `SafeCall.pcall()`.

### Example

```gdscript
extends Node

@onready var player_model = $Player

# A function that might crash if the node doesn't exist
func risky_function() -> void:
	var test_node: Node = player_model.get_node("Test")
	# If "Test" doesn't exist, this normally crashes the release build!
	test_node.get_children()

func _ready() -> void:
	# Safely call the function
	var res = SafeCall.pcall(risky_function, [])

	if res.ok:
		print("✅ Success! Got: ", res.result)
	else:
		print("❌ Caught error without crashing: ", res.error)
```

---

## 📋 Return Dictionary Structure

`SafeCall.pcall()` returns a dictionary with the following keys:

- `ok` (`bool`): `true` if the call succeeded without errors, `false` if an error was caught.
- `error` (`String`): A detailed error message if the call failed, for example `"Cannot call method 'get_children' on a null value."`. Empty if successful.
- `result` (`Variant`): The return value of your callable. `null` if the call failed.

---

## ⚙️ How It Works Under the Hood

1. **The C++ module**: Registers the `SafeCall` singleton. When `pcall` is invoked, it flips a `thread_local` boolean flag (`SafeCall::safe_mode = true`), executes the callable, and then flips it back. It also temporarily binds a custom Godot error handler to catch internal C++ error messages securely.
2. **The VM patch**: The `pcall_patch.py` script targets `gdscript_vm.cpp`. It finds blocks of code normally stripped out by `#ifdef DEBUG_ENABLED` and forces them to compile into release builds using explicit runtime evaluations instead of macro switches.
3. **The switch**: These injected checks are wrapped in an `if (unlikely(SafeCall::is_safe_mode()))` condition. Therefore, they are only evaluated while a `pcall` is active. If an error is detected, the VM gracefully aborts the current opcode (`OPCODE_BREAK`) instead of causing a C++ segmentation fault.

---

## 📜 License

This module is provided under the MIT License. Feel free to use, modify, and distribute it in your own Godot projects.
