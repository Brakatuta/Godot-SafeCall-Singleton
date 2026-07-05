#!/usr/bin/env python3
import argparse
import re
import sys

BEGIN = b"// >>> SAFE_CALL PATCH [{id}] >>>\n"
END = b"// <<< SAFE_CALL PATCH [{id}] <<<\n"

def wrap(patch_id: bytes, body: bytes) -> bytes:
    if not body.endswith(b"\n"):
        body = body + b"\n"
    return BEGIN.replace(b"{id}", patch_id) + body + END.replace(b"{id}", patch_id)

def marker_span(data: bytes, patch_id: bytes):
    b = BEGIN.replace(b"{id}", patch_id)
    e = END.replace(b"{id}", patch_id)
    i = data.find(b)
    if i == -1: return None
    j = data.find(e, i)
    return (i, j + len(e))

PATCH_0_ID = b"include"
PATCH_0_ANCHOR = (
    b'#include "core/os/os.h"\n'
    b'#include "core/profiling/profiling.h"\n'
)
PATCH_0_BODY = (
    b'#include "core/os/os.h"\n'
    b'#include "core/profiling/profiling.h"\n'
    b"\n"
    b'// FORCE ENABLED: safe_call module header\n'
    b'#include "modules/safe_call/safe_call.h"\n'
)

PATCH_1_ID = b"core_macros"
PATCH_1_ANCHOR = (
    b"#else // !DEBUG_ENABLED\n"
    b"#define GD_ERR_BREAK(m_cond)\n"
    b"#define CHECK_SPACE(m_space)\n"
    b"\n"
    b"#define GET_VARIANT_PTR(m_v, m_code_ofs) \\\n"
    b"\tVariant *m_v; \\\n"
    b"\t{ \\\n"
    b"\t\tint address = _code_ptr[ip + 1 + (m_code_ofs)]; \\\n"
    b"\t\tm_v = &variant_addresses[(address & ADDR_TYPE_MASK) >> ADDR_BITS][address & ADDR_MASK]; \\\n"
    b"\t\tif (unlikely(!m_v)) \\\n"
    b"\t\t\tOPCODE_BREAK; \\\n"
    b"\t}\n"
    b"\n"
    b"#endif // DEBUG_ENABLED\n"
)
PATCH_1_BODY = (
    b"#else // !DEBUG_ENABLED\n"
    b"// FORCE ENABLED: Runtime-conditional versions for SafeCall.\n"
    b"#define GD_ERR_BREAK(m_cond) \\\n"
    b"\t{ \\\n"
    b"\t\tif (unlikely(SafeCall::is_safe_mode() && (m_cond))) { \\\n"
    b"\t\t\t_err_print_error(FUNCTION_STR, __FILE__, __LINE__, \"Condition ' \" _STR(m_cond) \" ' is true. Breaking..:\"); \\\n"
    b"\t\t\tOPCODE_BREAK; \\\n"
    b"\t\t} \\\n"
    b"\t}\n"
    b"\n"
    b"#define CHECK_SPACE(m_space) \\\n"
    b"\tGD_ERR_BREAK((ip + m_space) > _code_size)\n"
    b"\n"
    b"#define GET_VARIANT_PTR(m_v, m_code_ofs) \\\n"
    b"\tVariant *m_v; \\\n"
    b"\t{ \\\n"
    b"\t\tint address = _code_ptr[ip + 1 + (m_code_ofs)]; \\\n"
    b"\t\tif (unlikely(SafeCall::is_safe_mode())) { \\\n"
    b"\t\t\tint address_type = (address & ADDR_TYPE_MASK) >> ADDR_BITS; \\\n"
    b"\t\t\tif (unlikely(address_type < 0 || address_type >= ADDR_TYPE_MAX)) { \\\n"
    b'\t\t\t\terr_text = "Bad address type."; \\\n'
    b"\t\t\t\tOPCODE_BREAK; \\\n"
    b"\t\t\t} \\\n"
    b"\t\t\tint address_index = address & ADDR_MASK; \\\n"
    b"\t\t\tif (unlikely(address_index < 0 || address_index >= variant_address_limits[address_type])) { \\\n"
    b"\t\t\t\tif (address_type == ADDR_TYPE_MEMBER && !p_instance) { \\\n"
    b'\t\t\t\t\terr_text = "Cannot access member without instance."; \\\n'
    b"\t\t\t\t} else { \\\n"
    b'\t\t\t\t\terr_text = "Bad address index."; \\\n'
    b"\t\t\t\t} \\\n"
    b"\t\t\t\tOPCODE_BREAK; \\\n"
    b"\t\t\t} \\\n"
    b"\t\t} \\\n"
    b"\t\tm_v = &variant_addresses[(address & ADDR_TYPE_MASK) >> ADDR_BITS][address & ADDR_MASK]; \\\n"
    b"\t\tif (unlikely(!m_v)) \\\n"
    b"\t\t\tOPCODE_BREAK; \\\n"
    b"\t}\n"
    b"#endif // DEBUG_ENABLED\n"
)

PATCH_2_ID = b"exit_ok_decl"
PATCH_2_ANCHOR = (
    b"\tif (GDScriptLanguage::get_singleton()->profiling) {\n"
    b"\t\tfunction_start_time = OS::get_singleton()->get_ticks_usec();\n"
    b"\t\tfunction_call_time = 0;\n"
    b"\t\tprofile.call_count.increment();\n"
    b"\t\tprofile.frame_call_count.increment();\n"
    b"\t}\n"
    b"\tbool exit_ok = false;\n"
    b"\tint variant_address_limits[ADDR_TYPE_MAX] = { _stack_size, _constant_count, p_instance ? (int)p_instance->members.size() : 0 };\n"
    b"#endif\n"
)
PATCH_2_BODY = (
    b"\tif (GDScriptLanguage::get_singleton()->profiling) {\n"
    b"\t\tfunction_start_time = OS::get_singleton()->get_ticks_usec();\n"
    b"\t\tfunction_call_time = 0;\n"
    b"\t\tprofile.call_count.increment();\n"
    b"\t\tprofile.frame_call_count.increment();\n"
    b"\t}\n"
    b"#endif\n"
    b"\t// Always declared: needed by the pcall runtime safety checks in release\n"
    b"\tbool exit_ok = false;\n"
    b"\tint variant_address_limits[ADDR_TYPE_MAX] = { _stack_size, _constant_count, p_instance ? (int)p_instance->members.size() : 0 };\n"
)

PATCH_3_ID = b"dispatch_loop"
PATCH_3_ANCHOR = (
    b"#ifdef DEBUG_ENABLED\n"
    b"\tOPCODE_WHILE(ip < _code_size) {\n"
    b"\t\tint last_opcode = _code_ptr[ip];\n"
    b"#else\n"
    b"\tOPCODE_WHILE(true) {\n"
    b"#endif\n"
)
PATCH_3_BODY = (
    b"// FORCE ENABLED: Bounds-checked dispatch loop for SafeCall\n"
    b"#if 1\n"
    b"\tOPCODE_WHILE(ip < _code_size) {\n"
    b"\t\tint last_opcode = _code_ptr[ip];\n"
    b"#else\n"
    b"\tOPCODE_WHILE(true) {\n"
    b"#endif\n"
)

PATCH_4_ID = b"exit_block"
PATCH_4_ANCHOR = b"#ifdef DEBUG_ENABLED\n\t\tif (exit_ok) {"
PATCH_4_BODY = b"#if 1 // FORCE ENABLED: Shared error-report/unwind block\n\t\tif (exit_ok) {"

PATCH_5_ID = b"exit_ok_sites"
PATCH_5_REGEX = re.compile(
    rb"#ifdef DEBUG_ENABLED\n(\t+)exit_ok = true;\n(#endif(?: // DEBUG_ENABLED)?)\n"
)
def patch_5_body(m: re.Match) -> bytes:
    indent, endif_text = m.group(1), m.group(2)
    return indent + b"exit_ok = true; // original: " + endif_text + b"\n"

PATCH_6_ID = b"null_check_sites"
PATCH_6_REGEX = re.compile(
    rb"#ifdef DEBUG_ENABLED\n"
    rb"(\t+)bool freed = false;\n"
    rb"\1Object \*base_obj = base->get_validated_object_with_check\(freed\);\n"
    rb"\1if \(freed\) \{\n"
    rb"\1\terr_text = METHOD_CALL_ON_FREED_INSTANCE_ERROR\(method\);\n"
    rb"\1\tOPCODE_BREAK;\n"
    rb"\1\} else if \(!base_obj\) \{\n"
    rb"\1\terr_text = METHOD_CALL_ON_NULL_VALUE_ERROR\(method\);\n"
    rb"\1\tOPCODE_BREAK;\n"
    rb"\1\}\n"
    rb"#else\n"
    rb"\1Object \*base_obj = (.+?);\n"
    rb"#endif\n"
)

def patch_6_body(m: re.Match) -> bytes:
    indent = m.group(1)
    fast_expr = m.group(2)
    return (
        b"#ifdef DEBUG_ENABLED\n"
        + indent + b"bool freed = false;\n"
        + indent + b"Object *base_obj = base->get_validated_object_with_check(freed);\n"
        + indent + b"if (freed) {\n"
        + indent + b"\terr_text = METHOD_CALL_ON_FREED_INSTANCE_ERROR(method);\n"
        + indent + b"\tOPCODE_BREAK;\n"
        + indent + b"} else if (!base_obj) {\n"
        + indent + b"\terr_text = METHOD_CALL_ON_NULL_VALUE_ERROR(method);\n"
        + indent + b"\tOPCODE_BREAK;\n"
        + indent + b"}\n"
        b"#else // FORCE ENABLED: SafeCall runtime check\n"
        + indent + b"Object *base_obj;\n"
        + indent + b"if (unlikely(SafeCall::is_safe_mode())) {\n"
        + indent + b"\tbool freed = false;\n"
        + indent + b"\tbase_obj = base->get_validated_object_with_check(freed);\n"
        + indent + b"\tif (freed) {\n"
        + indent + b"\t\terr_text = METHOD_CALL_ON_FREED_INSTANCE_ERROR(method);\n"
        + indent + b"\t\tOPCODE_BREAK;\n"
        + indent + b"\t} else if (!base_obj) {\n"
        + indent + b"\t\terr_text = METHOD_CALL_ON_NULL_VALUE_ERROR(method);\n"
        + indent + b"\t\tOPCODE_BREAK;\n"
        + indent + b"\t}\n"
        + indent + b"} else {\n"
        + indent + b"\tbase_obj = " + fast_expr + b";\n"
        + indent + b"}\n"
        b"#endif\n"
    )

SIMPLE_PATCHES = [
    (PATCH_0_ID, "Include SafeCall header", PATCH_0_ANCHOR, PATCH_0_BODY),
    (PATCH_1_ID, "Runtime-conditional GD_ERR_BREAK/CHECK_SPACE/GET_VARIANT_PTR", PATCH_1_ANCHOR, PATCH_1_BODY),
    (PATCH_2_ID, "Always declare exit_ok/variant_address_limits", PATCH_2_ANCHOR, PATCH_2_BODY),
    (PATCH_3_ID, "Bounds-checked dispatch loop + last_opcode tracking", PATCH_3_ANCHOR, PATCH_3_BODY),
    (PATCH_4_ID, "Enable shared error-report/unwind block", PATCH_4_ANCHOR, PATCH_4_BODY),
]

REGEX_PATCHES = [
    (PATCH_5_ID, "exit_ok = true; at return sites", PATCH_5_REGEX, patch_5_body, 8),
    (PATCH_6_ID, "Null/freed-object method-call checks", PATCH_6_REGEX, patch_6_body, 3),
]

def apply_simple(data: bytes, patch_id, desc, anchor, body, verbose=True) -> bytes:
    span = marker_span(data, patch_id)
    if span is not None:
        if verbose: print(f"[skip]  {patch_id.decode():20s} already applied - {desc}")
        return data
    count = data.count(anchor)
    if count == 0: raise RuntimeError(f"Patch '{patch_id.decode()}' ({desc}): anchor text not found.")
    if count > 1: raise RuntimeError(f"Patch '{patch_id.decode()}' ({desc}): anchor text found {count} times.")
    if verbose: print(f"[apply] {patch_id.decode():20s} {desc}")
    return data.replace(anchor, wrap(patch_id, body), 1)

def apply_regex(data: bytes, patch_id, desc, regex, body_fn, expected_count, verbose=True) -> bytes:
    prefix_marker = b"// >>> SAFE_CALL PATCH [" + patch_id + b"_"
    if prefix_marker in data:
        if verbose: print(f"[skip]  {patch_id.decode():20s} already applied - {desc}")
        return data
    matches = list(regex.finditer(data))
    if len(matches) != expected_count:
        raise RuntimeError(f"Patch '{patch_id.decode()}' ({desc}): found {len(matches)} matches, expected exactly {expected_count}.")
    out = data
    for m in reversed(matches):
        replacement = wrap(patch_id + b"_" + str(m.start()).encode(), body_fn(m))
        out = out[:m.start()] + replacement + out[m.end():]
    if verbose: print(f"[apply] {patch_id.decode():20s} {desc} ({len(matches)} sites)")
    return out

def cmd_add(data: bytes) -> bytes:
    for patch_id, desc, anchor, body in SIMPLE_PATCHES:
        data = apply_simple(data, patch_id, desc, anchor, body)
    for patch_id, desc, regex, body_fn, expected in REGEX_PATCHES:
        data = apply_regex(data, patch_id, desc, regex, body_fn, expected)
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", action="store_true")
    ap.add_argument("file")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        data = f.read()

    try:
        if args.add:
            new_data = cmd_add(data)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if new_data != data:
        with open(args.file, "wb") as f:
            f.write(new_data)
        print(f"\nWrote changes to {args.file}")

if __name__ == "__main__":
    main()