"""
Evaluate soundness of postconditions by detecting hallucinated identifiers.
A postcondition is unsound if it references undefined variables.
"""

import json
import ast
from pathlib import Path

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).parent.parent
GENERATED_POSTCONDITIONS_FILE = PROJECT_ROOT / "src" / "dataset" / "generated_postconditions.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "evaluation" / "soundness_report.json"

# Allowed built-in names
ALLOWED_BUILTINS = {
    "len", "all", "any", "sorted", "range", "min", "max", "sum", "abs",
    "set", "list", "tuple", "dict", "enumerate", "zip", "str", "int",
    "float", "bool", "type", "isinstance", "hasattr", "getattr",
    "map", "filter", "reversed", "ord", "chr", "round", "pow", "bin", "hex", "oct",
    "True", "False", "None"
}


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


def extract_function_params(function_code: str) -> set:
    """Extract all parameter names from the LAST function definition."""
    try:
        tree = ast.parse(function_code)
        
        # Find the LAST function defined (postconditions are for the last function)
        last_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                last_func = node
        
        if last_func:
            params = set()
            # Regular positional and keyword args
            for arg in last_func.args.args:
                params.add(arg.arg)
            # *args
            if last_func.args.vararg:
                params.add(last_func.args.vararg.arg)
            # **kwargs
            if last_func.args.kwarg:
                params.add(last_func.args.kwarg.arg)
            # Keyword-only args
            for arg in last_func.args.kwonlyargs:
                params.add(arg.arg)
            return params
    except:
        pass
    return set()


def extract_helper_functions(function_code: str) -> set:
    """Extract all helper function names defined in the same file."""
    try:
        tree = ast.parse(function_code)
        helper_funcs = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                helper_funcs.add(node.name)
        
        return helper_funcs
    except:
        return set()


def extract_referenced_names(postcondition_code: str) -> set:
    """
    Extract all names referenced (loaded) in the postcondition.
    Excludes loop variables from comprehensions/generators (they're locally scoped).
    """
    try:
        tree = ast.parse(postcondition_code, mode='exec')
        referenced = set()
        
        # Collect all comprehension/generator loop variables
        local_vars = set()
        for node in ast.walk(tree):
            # List/Set/Dict comprehensions and GeneratorExp all have 'generators'
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for generator in node.generators:
                    # Extract target variable names (can be Name, Tuple, List)
                    for target_node in ast.walk(generator.target):
                        if isinstance(target_node, ast.Name):
                            local_vars.add(target_node.id)
            # Lambda parameters are also local
            elif isinstance(node, ast.Lambda):
                for arg in node.args.args:
                    local_vars.add(arg.arg)
                if node.args.vararg:
                    local_vars.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_vars.add(node.args.kwarg.arg)
        
        # Now collect all loaded names, excluding local variables
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in local_vars:
                    referenced.add(node.id)
        
        return referenced
    except:
        return set()


def is_sound_postcondition(function_code: str, postcondition_code: str) -> tuple:
    """
    Check if a postcondition is sound (no hallucinated identifiers).
    Returns: (is_sound: bool, hallucinated_vars: set)
    """
    # Get allowed names
    params = extract_function_params(function_code)
    helper_funcs = extract_helper_functions(function_code)
    allowed_names = params | {"result"} | ALLOWED_BUILTINS | helper_funcs
    
    # Get referenced names
    referenced = extract_referenced_names(postcondition_code)
    
    # Find hallucinated names
    hallucinated = referenced - allowed_names
    
    is_sound = len(hallucinated) == 0
    return is_sound, hallucinated


def evaluate_soundness(generated_postconditions: list) -> dict:
    """Evaluate soundness of all postconditions."""
    print("\n=== Evaluating Soundness (Hallucination Detection) ===\n")
    
    soundness_report = {}
    
    for gen_post in generated_postconditions:
        task_id = gen_post["task_id"]
        function_code = gen_post["function_code"]
        postconditions = gen_post["generated_postconditions"]
        
        print(f"Evaluating function {task_id}...")
        
        task_results = {}
        for strategy in ["naive", "few_shot", "chain_of_thought"]:
            postcondition_code = postconditions.get(strategy, "")
            
            if not postcondition_code or "ERROR" in postcondition_code:
                task_results[strategy] = False
                print(f"  {strategy}: ✗ (error or missing)")
                continue
            
            # Check soundness
            is_sound, hallucinated = is_sound_postcondition(
                function_code, postcondition_code
            )
            
            task_results[strategy] = is_sound
            
            if is_sound:
                print(f"  {strategy}: ✓ (sound)")
            else:
                print(f"  {strategy}: ✗ (hallucinated: {hallucinated})")
        
        soundness_report[str(task_id)] = task_results
    
    return soundness_report


def main():
    """Main execution function."""
    print("=== Soundness Evaluation ===\n")
    
    # Load generated postconditions
    print("Loading generated postconditions...")
    generated_postconditions = load_json(GENERATED_POSTCONDITIONS_FILE)
    print(f"Loaded {len(generated_postconditions)} postconditions\n")
    
    # Evaluate soundness
    soundness_report = evaluate_soundness(generated_postconditions)
    
    # Calculate statistics
    total_functions = len(soundness_report)
    sound_counts = {"naive": 0, "few_shot": 0, "chain_of_thought": 0}
    
    for function_results in soundness_report.values():
        for strategy, is_sound in function_results.items():
            if is_sound:
                sound_counts[strategy] += 1
    
    print("\n=== Summary ===")
    for strategy in ["naive", "few_shot", "chain_of_thought"]:
        count = sound_counts[strategy]
        percentage = (count / total_functions) * 100 if total_functions > 0 else 0
        print(f"{strategy}: {count}/{total_functions} sound ({percentage:.1f}%)")
    
    # Save report
    save_json(OUTPUT_FILE, soundness_report)
    print(f"\n=== Soundness Evaluation Complete ===")
    print(f"Report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
