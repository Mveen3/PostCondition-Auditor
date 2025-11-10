# src/evaluate_correctness.py
import json
import ast
import re
import inspect
import textwrap
import math
import heapq
import sys
from types import FunctionType

from hypothesis import given, strategies as st, settings, HealthCheck, assume
import hypothesis.errors

# -------------------------------
# CONFIG
# -------------------------------
INPUT_FILE = "generated_postconditions.json"  # from your repo root (you run from project root)
OUTPUT_FILE = "correctness_results.json"
HYPOTHESIS_EXAMPLES = 150


# -------------------------------
# UTIL: Load JSON
# -------------------------------
def load_data(input_file):
    try:
        with open(input_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found → {input_file}")
        return None


# -------------------------------
# CLEAN ASSERTION STRING (robust)
# -------------------------------
def clean_assertion_string(s: str) -> str:
    if not s:
        return ""

    s = s.strip()

    # If the string begins with code fences, strip them
    # remove ```python ... ``` or ``` ... ```
    fence = re.match(r"^```(?:python)?\s*(.*)```$", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()

    # Remove leading 'assert ' if present
    if s.startswith("assert "):
        s = s[len("assert "):].strip()

    # Remove surrounding backticks
    s = s.strip("`").strip()

    # If the assertion came from "assert expr, 'msg'" remove trailing , 'msg'
    # Remove only the trailing comma + string-literal part, not internal commas in expressions.
    s = re.sub(r'\s*,\s*(?:["\']).*(?:["\'])\s*$', '', s)

    # Replace common alternate names with 'result' (if generated text used return_value)
    s = s.replace("return_value", "result")
    s = s.replace("return value", "result")
    s = s.rstrip(",")

    return s


# -------------------------------
# AST-BASED TYPE HINTING + name heuristics
# -------------------------------
def infer_param_type(function_code: str, param: str) -> str:
    """
    Try to infer whether 'param' is a 'list', 'string', 'tuple' or 'int' based on AST usage
    Fallback to a small name-based heuristic list for common parameter names.
    """
    # Simple name-based hints (fast fallback + covers many MBPP functions)
    name_hints_string = {"s", "str", "text", "word", "ch", "name"}
    name_hints_list = {"arr", "nums", "list", "lst", "list1", "listval", "dlist", "test_list", "test_tup", "test_tup1", "test_tup2", "numbers", "input_list", "listoflists"}
    name_hints_tuple = {"test_tup", "test_tup1", "test_tup2", "tup"}
    lower = param.lower()
    if lower in name_hints_string:
        return "string"
    if lower in name_hints_tuple:
        return "tuple"
    if lower in name_hints_list:
        return "list"

    # Try AST-based inference
    try:
        tree = ast.parse(textwrap.dedent(function_code))
    except Exception:
        return "int"

    seen_iter = False
    seen_index = False
    seen_str_ops = False
    seen_binop_add = False
    seen_len_call = False

    for node in ast.walk(tree):
        # for ... in param
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Name) and node.iter.id == param:
                seen_iter = True
            # for x in param[...] as well
            if isinstance(node.iter, ast.Subscript) and isinstance(getattr(node.iter, "value", None), ast.Name) and node.iter.value.id == param:
                seen_iter = True

        # param[i] style
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == param:
            seen_index = True

        # calls like param.split(), param.replace()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == param:
                if node.func.attr in {"split", "replace", "upper", "lower", "find", "startswith", "endswith", "strip", "isalnum", "isalpha"}:
                    seen_str_ops = True

        # Binary addition: str + str or param + something
        if isinstance(node, ast.BinOp) and isinstance(node.left, ast.Name) and node.left.id == param and isinstance(node.op, ast.Add):
            seen_binop_add = True
        if isinstance(node, ast.BinOp) and isinstance(node.right, ast.Name) and node.right.id == param and isinstance(node.op, ast.Add):
            seen_binop_add = True

        # len(param)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len":
            if len(node.args) >= 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == param:
                seen_len_call = True

    # Heuristics assembled
    if seen_str_ops or (seen_binop_add and not (seen_index or seen_iter)):
        return "string"
    if seen_iter or seen_index or seen_len_call:
        return "list"
    return "int"


def get_strategy_for_param(param: str, function_code: str):
    """
    Combines AST inference and name heuristics to return a hypothesis strategy
    that is *likely* to be compatible with the function parameter.
    """
    inferred = infer_param_type(function_code, param)

    if inferred == "string":
        # use plain text; avoid overly exotic unicode (keep tests stable)
        return st.text(min_size=0, max_size=40)

    if inferred == "tuple":
        # small tuples of ints by default
        return st.tuples(st.integers(min_value=-100, max_value=100), st.integers(min_value=-100, max_value=100))

    if inferred == "list":
        # lists whose elements are either ints, floats or simple tuples (handles matrices and nested lists)
        elem_strategy = st.one_of(
            st.integers(min_value=-100, max_value=100),
            st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False),
            st.tuples(st.integers(-50, 50), st.integers(-50, 50)),
            st.text(min_size=0, max_size=10)
        )
        return st.lists(elem_strategy, min_size=0, max_size=12)

    # Default: integer parameter (use non-negative by default because many functions index)
    return st.integers(min_value=0, max_value=2000)


# -------------------------------
# LOAD FUNCTION + SCOPE
# -------------------------------
def load_function_and_scope(code: str):
    """
    Execute the function code in a fresh 'scope' dict that already contains
    the common helper modules the assertions might use (math, re, heapq, sys).
    Returns (callable_obj, scope_dict)
    """
    scope = {
        "__builtins__": __builtins__,
        "math": math,
        "re": re,
        "heapq": heapq,
        "hq": heapq,
        "sys": sys,
    }

    code = textwrap.dedent(code)

    try:
        # Execute code in scope (both functions and helper defs will be placed in scope)
        exec(code, scope)
    except Exception as e:
        # Return None function and the scope so caller can decide
        print(f"  - WARNING: exec() raised while loading function: {e}")
        return None, scope

    # Find the user-defined function object(s) in scope
    funcs = []
    for name, val in scope.items():
        # collect only user-defined functions (exclude imported modules)
        if isinstance(val, FunctionType):
            funcs.append((name, val))

    # If multiple functions in a code snippet, prefer the first non-helper function:
    # Heuristic: pick the function whose name is not 'binary_search' helper when there is a main function present.
    if not funcs:
        return None, scope

    # Pick the function which appears first in the code by scanning AST for def order
    try:
        parsed = ast.parse(code)
        def_names = [node.name for node in parsed.body if isinstance(node, ast.FunctionDef)]
        for dn in def_names:
            for name, fn in funcs:
                if name == dn:
                    return fn, scope
    except Exception:
        # fallback to first found function
        return funcs[0][1], scope

    # final fallback
    return funcs[0][1], scope


# -------------------------------
# BUILD + RUN HYPO TEST
# -------------------------------
def build_and_run_test(func, scope, assertion, function_code, task_id):
    cleaned = clean_assertion_string(assertion)

    if not cleaned:
        return "untestable_empty"

    # Quick sanity: parsed AST expression (must be evaluable)
    try:
        ast.parse(cleaned)
    except Exception:
        return "untestable_syntax"

    # Parameter names
    try:
        param_names = list(inspect.signature(func).parameters.keys())
    except (ValueError, TypeError):
        return "error_signature"

    # Build Hypothesis test dynamically
    @settings(
        max_examples=HYPOTHESIS_EXAMPLES,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        deadline=5000
    )
    @given(**{p: get_strategy_for_param(p, function_code) for p in param_names})
    def dyn_test(**kwargs):
        # defensively execute: if the chosen input causes obvious runtime errors (IndexError, TypeError,
        # ValueError, KeyError) we ask Hypothesis to discard this example (assume(False)) and try others.
        try:
            result = func(**kwargs)
        except (IndexError, TypeError, ValueError, KeyError) as e:
            # discard the example (not a real "failure" of the postcondition — just incompatible input)
            assume(False)  # tell Hypothesis to skip this example
            return
        except Exception as e:
            # other unexpected exceptions should be surfaced so the test marks fail
            raise

        # Build local scope for eval: parameters + result
        local_scope = kwargs.copy()
        local_scope["result"] = result

        # Evaluate the assertion in the context (scope as globals, local_scope as locals)
        try:
            ok = eval(cleaned, scope, local_scope)
        except NameError as e:
            # If eval refers to a name not in scope, try to give a clearer message in the debug log, then fail
            raise
        except Exception:
            # treat any exception while evaluating assertion as test failure
            raise

        # If the assertion expression evaluates to something truthy that's ok.
        # If it returns None (happens when original used 'assert' incorrectly), treat as failure.
        if not bool(ok):
            # explicit assertion failure
            raise AssertionError("Postcondition returned False")

    # Run and capture result
    try:
        dyn_test()
        return "pass"
    except hypothesis.errors.FailedHealthCheck:
        return "error_healthcheck"
    except AssertionError:
        return "fail"
    except Exception as e:
        # catch-all: include the exception string for easier debugging
        return "error_eval"


# -------------------------------
# MAIN
# -------------------------------
def main():
    data = load_data(INPUT_FILE)
    if not data:
        print("No input data.")
        return

    final_results = []

    for item in data:
        task_id = item.get("task_id")
        function_code = item.get("function_code")
        postconds = item.get("generated_postconditions", {})

        # load function and scope
        func, scope = load_function_and_scope(function_code)

        if func is None:
            r = {k: "error_loading_function" for k in postconds}
            final_results.append({"task_id": task_id, "results": r})
            continue

        result_dict = {}

        for strategy, assertion in postconds.items():
            try:
                result = build_and_run_test(func, scope, assertion, function_code, task_id)
            except Exception:
                result = "error_eval"
            result_dict[strategy] = result

        final_results.append({"task_id": task_id, "results": result_dict})

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_results, f, indent=2)

    print(f"\n✅ Evaluation complete. Results saved to {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
