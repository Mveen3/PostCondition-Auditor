"""
Evaluate correctness of generated postconditions using concrete test cases.
Generates 1000 test cases per function using Hypothesis property-based testing.
"""

import json
import ast
from pathlib import Path
from hypothesis import given, strategies as st, settings, Phase, Verbosity, HealthCheck
from hypothesis.strategies import SearchStrategy
import sys
import warnings

# Suppress repetitive SyntaxWarnings from functions with invalid escape sequences
warnings.filterwarnings("ignore", category=SyntaxWarning)

NUM_TEST_CASES = 1000
PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_MBPP_FILE = PROJECT_ROOT / "src" / "dataset" / "processed_mbpp.json"
GENERATED_POSTCONDITIONS_FILE = PROJECT_ROOT / "src" / "dataset" / "generated_postconditions.json"
TEST_CASES_FILE = PROJECT_ROOT / "src" / "dataset" / "test_cases.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "reports" / "correctness_report.json"


def load_json(file_path: Path) -> any:
    """Load JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(file_path: Path, data: any):
    """Save data to JSON file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_function_name(function_code: str) -> str:
    """Extract function name from function code. Returns the LAST function defined."""
    try:
        tree = ast.parse(function_code)
        funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if funcs:
            return funcs[-1]
    except:
        import re
        matches = re.findall(r'def\s+(\w+)\s*\(', function_code)
        if matches:
            return matches[-1]
    raise ValueError(f"Could not extract function name from: {function_code[:100]}")


def extract_function_params(function_code: str) -> list:
    """Extract function parameter names from the LAST function defined."""
    try:
        tree = ast.parse(function_code)
        funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if funcs:
            return [arg.arg for arg in funcs[-1].args.args]
    except:
        pass
    return []


def is_recursive_function(function_code: str, function_name: str) -> bool:
    """Check if a function is recursive by looking for self-calls."""
    split_code = function_code.split(f'def {function_name}')
    return function_name in split_code[1] if len(split_code) > 1 else False


def infer_strategy_from_mbpp(task: dict) -> dict:
    """Infer Hypothesis strategies from MBPP test cases."""
    test_list = task.get("test_list", [])
    params = extract_function_params(task["code"])
    function_code = task["code"]
    function_name = extract_function_name(function_code)
    is_recursive = is_recursive_function(function_code, function_name)
    
    param_strategies = {}
    param_example_types = {}  # Track if we see tuples vs lists
    param_example_values = {}  # Track all example values for each parameter
    
    # Parse test cases to infer types
    for test_str in test_list:
        try:
            test_str = test_str.strip()
            if test_str.startswith('assert '):
                test_str = test_str[7:].strip()
            
            if '==' in test_str:
                func_call = test_str.split('==')[0].strip()
                
                if '(' in func_call and ')' in func_call:
                    args_str = func_call[func_call.index('(') + 1:func_call.rindex(')')].strip()
                    
                    if args_str:
                        try:
                            eval_globals = {"__builtins__": {}}
                            args = eval(f"[{args_str}]", eval_globals)
                            
                            # Infer strategy for each parameter based on example values
                            for i, (param, value) in enumerate(zip(params, args)):
                                if i < len(params):
                                    # Track type consistency (tuple vs list)
                                    if param not in param_example_types:
                                        param_example_types[param] = type(value)
                                    
                                    # Collect all example values for constraint detection
                                    if param not in param_example_values:
                                        param_example_values[param] = []
                                    param_example_values[param].append(value)
                                    
                                    if param not in param_strategies:
                                        param_strategies[param] = infer_strategy_from_value(
                                            value, param, is_recursive, function_code
                                        )
                        except:
                            continue
        except:
            continue
    
    # Detect parameters with highly constrained values (same value in all examples)
    for param, values in param_example_values.items():
        if len(values) >= 2:
            # Check if all values are identical (highly constrained parameter)
            try:
                # For simple types, check equality directly
                if all(v == values[0] for v in values):
                    # Use sampled_from with just the observed value(s)
                    param_strategies[param] = st.sampled_from([values[0]])
                    continue
            except (TypeError, ValueError):
                # For unhashable types (lists, dicts), convert to string for comparison
                if all(str(v) == str(values[0]) for v in values):
                    param_strategies[param] = st.sampled_from([values[0]])
                    continue
            
            # Check if parameter has very few unique values (e.g., always 2 or always from {1,2,3})
            try:
                unique_count = len(set(v if not isinstance(v, list) else str(v) for v in values))
                if unique_count <= 3:
                    # Deduplicate values while preserving order
                    seen = set()
                    unique_vals = []
                    for v in values:
                        v_key = v if not isinstance(v, (list, dict)) else str(v)
                        if v_key not in seen:
                            seen.add(v_key)
                            unique_vals.append(v)
                    param_strategies[param] = st.sampled_from(unique_vals)
            except (TypeError, ValueError):
                pass  # Skip if comparison fails
    
    # Fallback to name-based strategies for missing parameters
    for param in params:
        if param not in param_strategies:
            param_strategies[param] = infer_strategy_from_name(param, is_recursive)
    
    # Post-process: If we detected tuples in examples, ensure we generate tuples not lists
    for param, strategy in param_strategies.items():
        if param in param_example_types and param_example_types[param] == tuple:
            # Convert list strategy to tuple strategy
            strategy_str = str(strategy)
            if 'lists(' in strategy_str:
                # Create tuple of same elements instead of list
                # For tuples with mixed numeric types, create a flexible tuple strategy
                param_strategies[param] = st.tuples(
                    st.one_of(
                        st.integers(min_value=-100, max_value=100),
                        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
                    ),
                    st.one_of(
                        st.integers(min_value=-100, max_value=100),
                        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
                    ),
                    st.one_of(
                        st.integers(min_value=-100, max_value=100),
                        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
                    )
                )
    
    return param_strategies


def infer_strategy_from_value(value, param_name: str, is_recursive: bool, function_code: str = "") -> SearchStrategy:
    """Infer a Hypothesis strategy from an example value."""
    param_lower = param_name.lower()
    
    if isinstance(value, list):
        if not value:
            return st.lists(st.text(max_size=20) if 'str' in param_lower else st.integers(-100, 100), max_size=15)
        elem = value[0]
        if isinstance(elem, int):
            limit = min(max((abs(v) for v in value if isinstance(v, int)), default=100) * 2, 100)
            return st.lists(st.integers(-limit, limit), max_size=15)
        elif isinstance(elem, str):
            max_len = max((len(v) for v in value if isinstance(v, str)), default=20)
            return st.lists(st.text(max_size=max_len + 5), max_size=15)
        elif isinstance(elem, (list, tuple)):
            return st.lists(st.lists(st.integers(-50, 50), max_size=10), max_size=10)
        return st.lists(st.integers(-100, 100), max_size=15)
    
    elif isinstance(value, str):
        return st.text(min_size=0, max_size=min(max(len(value), 5) * 2, 50))
    
    elif isinstance(value, int):
        if is_recursive or any(k in param_lower for k in ['limit', 'max', 'bound']):
            # For limits in recursive or bounded functions, use smaller range
            # Check if examples are large (> 100) which indicates expensive computation
            if value > 100:
                return st.integers(1, 50)  # Much smaller range for expensive functions
            return st.integers(0, 20)
        max_val = abs(value) * 3 if value else 100
        return st.integers(-min(max_val, 200), min(max_val, 200))
    
    elif isinstance(value, float):
        return st.floats(-1000.0, 1000.0, allow_nan=False, allow_infinity=False)
    
    elif isinstance(value, bool):
        return st.booleans()
    
    elif isinstance(value, tuple):
        if not value:
            return st.tuples()
        strats = []
        for elem in value:
            if isinstance(elem, int):
                strats.append(st.integers(-50, 50))
            elif isinstance(elem, float):
                strats.append(st.floats(-100.0, 100.0, allow_nan=False, allow_infinity=False))
            elif isinstance(elem, str):
                strats.append(st.text(max_size=20))
            elif isinstance(elem, list):
                strats.append(st.lists(st.integers(-50, 50), max_size=10))
            elif isinstance(elem, bool):
                strats.append(st.booleans())
            else:
                strats.append(st.integers(-50, 50))
        return st.tuples(*strats)
    
    elif isinstance(value, dict):
        return st.dictionaries(st.text(min_size=1, max_size=10), st.integers(-100, 100), max_size=10)
    
    return st.integers(-100, 100)


def infer_strategy_from_name(param_name: str, is_recursive: bool) -> SearchStrategy:
    """Infer a Hypothesis strategy from parameter name when no examples available."""
    param_lower = param_name.lower()
    numeric_strat = st.one_of(st.integers(-100, 100), st.floats(-100.0, 100.0, allow_nan=False, allow_infinity=False))
    
    if any(k in param_lower for k in ['tup', 'pair', 'numbers']):
        return st.tuples(numeric_strat, numeric_strat, numeric_strat)
    elif any(k in param_lower for k in ['list', 'arr', 'nums', 'array']):
        return st.lists(st.integers(-100, 100), max_size=15)
    elif any(k in param_lower for k in ['str', 'text', 'word', 'char', 'name']):
        return st.text(min_size=0, max_size=50)
    elif 'dict' in param_lower or 'map' in param_lower or param_lower == 'data':
        return st.dictionaries(st.text(min_size=1, max_size=10), st.integers(-100, 100), max_size=10)
    elif any(k in param_lower for k in ['bool', 'flag', 'is_']):
        return st.booleans()
    elif any(k in param_lower for k in ['float', 'decimal', 'height', 'weight']):
        return st.floats(0.0, 200.0, allow_nan=False, allow_infinity=False)
    elif any(k in param_lower for k in ['n', 'num', 'count', 'size', 'len']):
        return st.integers(1, 15)
    else:
        return st.integers(0, 20) if (is_recursive or any(k in param_lower for k in ['limit', 'max', 'bound'])) else st.integers(-200, 200)


def parse_mbpp_test_cases(task: dict) -> list:
    """Extract test inputs from MBPP test_list."""
    test_inputs = []
    for test_str in task.get("test_list", []):
        try:
            test_str = test_str.strip().removeprefix('assert ')
            if '==' in test_str and '(' in test_str:
                func_call = test_str.split('==')[0].strip()
                args_str = func_call[func_call.index('(') + 1:func_call.rindex(')')].strip()
                if args_str:
                    args = eval(f"[{args_str}]", {"__builtins__": {}})
                    test_inputs.append(args)
        except:
            continue
    return test_inputs


def generate_test_cases_for_task_ID(task: dict, num_cases: int = NUM_TEST_CASES) -> dict:
    """Generate test cases for a single function using Hypothesis property-based testing.
    
    Will keep generating until reaching num_cases or detecting infinite loop (stalling).
    """
    import signal
    
    task_id = task["task_id"]
    function_code = task["code"]
    function_name = extract_function_name(function_code)
    
    print(f"  Generating {num_cases} test cases for function {function_name} (task {task_id})...")
    
    # Execute function with each input to get expected output
    test_cases = []
    exec_globals = {}
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Function execution timed out")
    
    try:
        # Suppress warnings during function execution (e.g., invalid escape sequences)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            exec(function_code, exec_globals)
        func = exec_globals[function_name]
        
        # Keep generating until we have enough test cases
        prev_count = 0
        stalled_batches = 0
        MAX_STALLED_BATCHES = 50  # Only stop if truly stuck (infinite loop protection)
        
        # Infer Hypothesis strategies from MBPP test cases (once)
        param_strategies = infer_strategy_from_mbpp(task)
        
        # Start with MBPP test cases as seeds
        mbpp_inputs = parse_mbpp_test_cases(task)
        initial_inputs = mbpp_inputs.copy()
        
        # Track total time spent to prevent hanging on expensive functions
        import time
        start_time = time.time()
        MAX_GENERATION_TIME = 900  # 15 minutes max per function
        
        while len(test_cases) < num_cases:
            # Check if we've spent too long on this function
            if time.time() - start_time > MAX_GENERATION_TIME:
                print(f"\r    Warning: Generation timeout after {MAX_GENERATION_TIME}s (expensive function)")
                print(f"    Stopping at {len(test_cases)} cases - function is computationally expensive")
                break
            
            # Generate a new batch of test inputs
            batch_size = num_cases - len(test_cases)
            
            # Use MBPP seeds for first batch, then generate with Hypothesis
            if initial_inputs:
                test_inputs = initial_inputs
                initial_inputs = []  # Use seeds only once
            else:
                # Generate inputs using Hypothesis
                test_inputs = []
                params = list(param_strategies.keys())
                
                if params:
                    @settings(
                        max_examples=batch_size * 2,
                        database=None,
                        phases=[Phase.generate],
                        verbosity=Verbosity.quiet,
                        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much, HealthCheck.data_too_large],
                        deadline=None
                    )
                    @given(**param_strategies)
                    def generate_batch(**generated_params):
                        args = [generated_params[param] for param in params]
                        test_inputs.append(args)
                    
                    try:
                        generate_batch()
                    except Exception as e:
                        pass  # Continue with empty test_inputs
            
            if not test_inputs:
                print(f"    Warning: Failed to generate test inputs")
                stalled_batches += 1
                if stalled_batches >= MAX_STALLED_BATCHES:
                    print(f"    Stopping: Cannot generate more inputs (protection from infinite loop)")
                    break
                continue
            
            # Try to execute each input
            for input_args in test_inputs:
                if len(test_cases) >= num_cases:
                    break
                    
                # Set timeout BEFORE any processing to catch all slow operations
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(5)  # 5 second timeout per test case (reduced from 10)
                
                try:
                    # Handle both single arg and multiple args
                    if not isinstance(input_args, list):
                        input_args = [input_args]
                    
                    try:
                        result = func(*input_args)
                        signal.alarm(0)  # Cancel timeout
                        
                        # Convert result to JSON-serializable format
                        if hasattr(result, '__iter__') and not isinstance(result, (str, list, dict, tuple)):
                            # Convert generators, iterators, etc. to lists
                            try:
                                result = list(result)
                            except:
                                continue  # Skip if can't convert
                        
                        # Skip non-serializable results
                        try:
                            json.dumps(result)  # Test if serializable
                        except (TypeError, ValueError):
                            continue
                        
                        test_cases.append({
                            "args": input_args,
                            "expected": result
                        })
                        
                    except TimeoutError:
                        signal.alarm(0)
                        continue  # Skip inputs that cause infinite loops
                        
                except Exception as e:
                    signal.alarm(0)
                    # Skip inputs that cause errors in original function
                    continue
            
            # Check if we're making progress (infinite loop protection)
            if len(test_cases) == prev_count:
                stalled_batches += 1
                if stalled_batches >= MAX_STALLED_BATCHES:
                    print(f"\r    Warning: No progress after {stalled_batches} batches (infinite loop protection)")
                    print(f"    Stopping at {len(test_cases)} cases - function may require specific input constraints")
                    break
            else:
                stalled_batches = 0  # Reset counter when we make progress
            
            # Show real-time progress on same line
            if len(test_cases) != prev_count:
                elapsed = time.time() - start_time
                print(f"\r    Progress: {len(test_cases)}/{num_cases} test cases ({elapsed:.1f}s elapsed)", end='', flush=True)
            
            prev_count = len(test_cases)
                
    except Exception as e:
        print(f"    Error executing function: {e}")
    finally:
        signal.alarm(0)  # Ensure alarm is cancelled
    
    # Report results
    if len(test_cases) < num_cases:
        print(f"\r    ⚠ Only generated {len(test_cases)}/{num_cases} test cases")
    else:
        print(f"\r    ✓ Generated {len(test_cases)} valid test cases")
    
    return {
        "task_id": task_id,
        "function_name": function_name,
        "test_cases": test_cases
    }


def load_or_generate_test_cases(generated_postconditions: list) -> dict:
    """Load existing test cases or generate new ones using Hypothesis.
    Prompts user if test cases already exist.
    """
    # Try to load existing test cases
    if TEST_CASES_FILE.exists():
        print("Checking existing test cases file...")
        test_cases_list = load_json(TEST_CASES_FILE)
        test_cases_dict = {tc["task_id"]: tc for tc in test_cases_list}
        
        # Check if we have test cases for all functions with exactly 1000 each
        all_task_ids = {gen_post["task_id"] for gen_post in generated_postconditions}
        existing_task_ids = set(test_cases_dict.keys())
        
        if all_task_ids == existing_task_ids:
            # Check if all tasks have exactly 1000 test cases
            all_complete = all(
                len(tc["test_cases"]) == NUM_TEST_CASES 
                for tc in test_cases_dict.values()
            )
            
            if all_complete:
                print(f"✓ Found complete test cases for all {len(generated_postconditions)} functions ({NUM_TEST_CASES} each)")
                print("\nDo you want to:")
                print("  1) Use existing test cases [default]")
                print("  2) Regenerate all test cases")
                
                while True:
                    try:
                        choice = input("\nEnter choice (1 or 2) [1]: ").strip()
                        if choice == "" or choice == "1":
                            print("Using existing test cases.\n")
                            return test_cases_dict
                        elif choice == "2":
                            print("Regenerating all test cases...\n")
                            break
                        else:
                            print("Invalid choice. Please enter 1 or 2, or press Enter for default.")
                    except (EOFError, KeyboardInterrupt):
                        print("\nUsing existing test cases (default).\n")
                        return test_cases_dict
            else:
                incomplete = [
                    (tc["task_id"], len(tc["test_cases"])) 
                    for tc in test_cases_dict.values() 
                    if len(tc["test_cases"]) != NUM_TEST_CASES
                ]
                print(f"⚠ Some functions don't have exactly {NUM_TEST_CASES} test cases:")
                for task_id, count in incomplete[:5]:
                    print(f"   Task {task_id}: {count} cases")
                if len(incomplete) > 5:
                    print(f"   ... and {len(incomplete) - 5} more")
                print("\nDo you want to:")
                print("  1) Use existing test cases anyway [default]")
                print("  2) Regenerate all test cases to reach 1000 for each")
                
                while True:
                    try:
                        choice = input("\nEnter choice (1 or 2) [1]: ").strip()
                        if choice == "" or choice == "1":
                            print("Using existing incomplete test cases.\n")
                            return test_cases_dict
                        elif choice == "2":
                            print("Regenerating all test cases...\n")
                            break
                        else:
                            print("Invalid choice. Please enter 1 or 2, or press Enter for default.")
                    except (EOFError, KeyboardInterrupt):
                        print("\nUsing existing test cases (default).\n")
                        return test_cases_dict
        else:
            missing_count = len(all_task_ids - existing_task_ids)
            print(f"⚠ Missing test cases for {missing_count} functions")
            print("Will regenerate all test cases.\n")
    else:
        print("No existing test cases found.\n")
    
    # Generate test cases for ALL functions (to ensure we have 1000 for each)
    print(f"Generating test cases for all {len(generated_postconditions)} functions...")
    print(f"Target: {NUM_TEST_CASES} test cases per function\n")
    
    test_cases_dict = {}
    for i, gen_post in enumerate(generated_postconditions, 1):
        print(f"[{i}/{len(generated_postconditions)}] Task {gen_post['task_id']}")
        task = {
            "task_id": gen_post["task_id"],
            "code": gen_post["function_code"],
            "test_list": gen_post.get("test_list", [])
        }
        tc = generate_test_cases_for_task_ID(task, NUM_TEST_CASES)
        test_cases_dict[gen_post["task_id"]] = tc
    
    # Save all test cases
    test_cases_list = list(test_cases_dict.values())
    save_json(TEST_CASES_FILE, test_cases_list)
    print(f"\n✓ Saved test cases for all {len(test_cases_list)} functions to {TEST_CASES_FILE}")
    
    return test_cases_dict


def evaluate_postcondition_on_test_case(function_code: str, postcondition_code: str, 
                                        test_case: dict) -> bool:
    """
    Evaluate a postcondition on a single test case.
    Returns True if postcondition passes, False if it fails or errors.
    """
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Postcondition evaluation timed out")
    
    try:
        # Set timeout to prevent infinite loops
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)  # 5 second timeout per test case evaluation
        
        # Create execution environment
        exec_globals = {}
        # Suppress warnings during function execution (e.g., invalid escape sequences)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            exec(function_code, exec_globals)
        
        # Get function
        func_name = extract_function_name(function_code)
        func = exec_globals[func_name]
        
        # Execute function with test inputs
        args = test_case["args"]
        result = func(*args)
        
        # Build evaluation environment for postcondition
        eval_env = exec_globals.copy()
        eval_env["result"] = result
        
        # Bind parameters to their values
        params = extract_function_params(function_code)
        for i, param in enumerate(params):
            if i < len(args):
                eval_env[param] = args[i]
        
        # Execute postcondition
        exec(postcondition_code, eval_env)
        
        signal.alarm(0)  # Cancel timeout
        return True
    except AssertionError:
        signal.alarm(0)
        return False
    except TimeoutError:
        signal.alarm(0)
        return False
    except Exception:
        signal.alarm(0)
        return False


def evaluate_correctness(generated_postconditions: list, test_cases_dict: dict) -> dict:
    """Evaluate correctness of all postconditions."""
    print("\n=== Evaluating Correctness ===\n")
    
    MAX_TEST_CASES_PER_EVAL = 1000  # If needed Limit test cases to prevent excessive runtime
    correctness_report = {}
    total_tasks = len(generated_postconditions)
    
    for idx, gen_post in enumerate(generated_postconditions, 1):
        task_id = gen_post["task_id"]
        function_code = gen_post["function_code"]
        postconditions = gen_post["generated_postconditions"]
        
        print(f"[{idx}/{total_tasks}] Evaluating task {task_id}...")
        
        # Get test cases
        if task_id not in test_cases_dict:
            print(f"  Warning: No test cases found for task {task_id}")
            continue
        
        test_cases = test_cases_dict[task_id]["test_cases"]
        
        # Limit test cases for efficiency
        if len(test_cases) > MAX_TEST_CASES_PER_EVAL:
            test_cases = test_cases[:MAX_TEST_CASES_PER_EVAL]
            print(f"  Using {MAX_TEST_CASES_PER_EVAL}/{len(test_cases_dict[task_id]['test_cases'])} test cases")
        
        task_results = {}
        for strategy in ["naive", "few_shot", "chain_of_thought"]:
            postcondition_code = postconditions.get(strategy, "")
            
            if not postcondition_code or "ERROR" in postcondition_code:
                task_results[strategy] = False
                print(f"  {strategy}: ✗ (no valid postcondition)")
                continue
            
            # Test postcondition on all test cases
            all_passed = True
            passed_count = 0
            
            try:
                for i, test_case in enumerate(test_cases):
                    # Progress indicator for long evaluations
                    if i > 0 and i % 25 == 0:
                        print(f"    {strategy}: {i}/{len(test_cases)} tests...", end='\r')
                    
                    passed = evaluate_postcondition_on_test_case(
                        function_code, postcondition_code, test_case
                    )
                    if passed:
                        passed_count += 1
                    else:
                        all_passed = False
                        break
                
                task_results[strategy] = all_passed
                status = "✓" if all_passed else "✗"
                print(f"  {strategy}: {status} ({passed_count}/{len(test_cases)} passed)")
                
            except Exception as e:
                print(f"  {strategy}: ✗ (evaluation error: {str(e)[:50]})")
                task_results[strategy] = False
        
        correctness_report[str(task_id)] = task_results
    
    return correctness_report


def main():
    """Main execution function."""
    print("=== Correctness Evaluation ===")
    print(f"Test cases per function: {NUM_TEST_CASES}")
    print("Generation method: Hypothesis property-based testing\n")
    
    # Load datasets
    print("Loading datasets...")
    processed_mbpp = load_json(PROCESSED_MBPP_FILE)
    generated_postconditions = load_json(GENERATED_POSTCONDITIONS_FILE)
    
    # Merge test_list from processed_mbpp into generated_postconditions
    mbpp_dict = {task["task_id"]: task for task in processed_mbpp}
    for gen_post in generated_postconditions:
        task_id = gen_post["task_id"]
        if task_id in mbpp_dict:
            gen_post["test_list"] = mbpp_dict[task_id].get("test_list", [])
    
    print(f"Loaded {len(generated_postconditions)} functions with postconditions\n")
    
    # Load or generate test cases
    test_cases_dict = load_or_generate_test_cases(generated_postconditions)
    
    # Evaluate correctness
    correctness_report = evaluate_correctness(generated_postconditions, test_cases_dict)
    
    # Save report
    save_json(OUTPUT_FILE, correctness_report)
    print(f"\n=== Correctness Evaluation Complete ===")
    print(f"Report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
