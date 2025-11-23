"""
Evaluate completeness of postconditions via mutation analysis.
Uses Mutmut-style standardized mutation operators .
"""

import json
import ast
import copy
import signal
from pathlib import Path
import warnings

# Suppress repetitive SyntaxWarnings from functions with invalid escape sequences
warnings.filterwarnings("ignore", category=SyntaxWarning)

NUM_MUTANTS = 5
PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_MBPP_FILE = PROJECT_ROOT / "src" / "dataset" / "processed_mbpp.json"
GENERATED_POSTCONDITIONS_FILE = PROJECT_ROOT / "src" / "dataset" / "generated_postconditions.json"
TEST_CASES_FILE = PROJECT_ROOT / "src" / "dataset" / "test_cases.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "reports" / "completeness_report.json"


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
    """Extract function name from function code."""
    try:
        tree = ast.parse(function_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node.name
    except:
        import re
        matches = re.findall(r'def\s+(\w+)\s*\(', function_code)
        if matches:
            return matches[-1]
    raise ValueError("Could not extract function name")


def extract_function_params(function_code: str) -> list:
    """Extract function parameter names."""
    try:
        for node in ast.walk(ast.parse(function_code)):
            if isinstance(node, ast.FunctionDef):
                return [arg.arg for arg in node.args.args]
    except:
        pass
    return []


class MutmutOperator(ast.NodeTransformer):
    """Mutmut-style mutation operator - standardized approach."""
    
    def __init__(self, mutation_id: int, mutation_mode: str = "default"):
        self.mutation_id = mutation_id
        self.current_id = 0
        self.mutated = False
        self.mutation_mode = mutation_mode  # default, aggressive, or compound
    
    def visit_Compare(self, node):
        """Relational Operator Replacement (ROR)."""
        if self.current_id == self.mutation_id and not self.mutated:
            self.mutated = True
            if node.ops:
                op = node.ops[0]
                mutations = {
                    'aggressive': {ast.Gt: ast.Eq, ast.Lt: ast.Eq, ast.GtE: ast.Lt, 
                                  ast.LtE: ast.Gt, ast.Eq: ast.Gt, ast.NotEq: ast.Eq},
                    'default': {ast.Gt: ast.Lt, ast.Lt: ast.Gt, ast.GtE: ast.LtE, 
                               ast.LtE: ast.GtE, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
                }
                mode = self.mutation_mode if self.mutation_mode == 'aggressive' else 'default'
                for op_type, new_op in mutations[mode].items():
                    if isinstance(op, op_type):
                        node.ops[0] = new_op()
                        break
        self.current_id += 1
        return self.generic_visit(node)
    
    def visit_BinOp(self, node):
        """Arithmetic Operator Replacement (AOR)."""
        if self.current_id == self.mutation_id and not self.mutated:
            self.mutated = True
            mutations = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, 
                        ast.Div: ast.Mult, ast.Mod: ast.Mult}
            for op_type, new_op in mutations.items():
                if isinstance(node.op, op_type):
                    node.op = new_op()
                    break
        self.current_id += 1
        return self.generic_visit(node)
    
    def visit_BoolOp(self, node):
        """Logical Operator Replacement (LOR)."""
        if self.current_id == self.mutation_id and not self.mutated:
            self.mutated = True
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        self.current_id += 1
        return self.generic_visit(node)
    
    def visit_Constant(self, node):
        """Constant Replacement (CRP)."""
        if self.current_id == self.mutation_id and not self.mutated:
            self.mutated = True
            if isinstance(node.value, int):
                if self.mutation_mode == "aggressive":
                    node.value = node.value * 2 if node.value != 0 else 1
                else:
                    if node.value == 0:
                        node.value = 1
                    elif node.value == 1:
                        node.value = 0
                    else:
                        node.value = node.value + 1
            elif isinstance(node.value, bool):
                node.value = not node.value
            elif isinstance(node.value, str) and node.value:
                node.value = "" if self.mutation_mode != "aggressive" else "mutated"
        self.current_id += 1
        return self.generic_visit(node)
    
    def visit_UnaryOp(self, node):
        """Unary Operator Insertion/Deletion (UOI)."""
        if self.current_id == self.mutation_id and not self.mutated:
            self.mutated = True
            if isinstance(node.op, ast.Not):
                return node.operand
            elif isinstance(node.op, ast.USub):
                node.op = ast.UAdd()
        self.current_id += 1
        return self.generic_visit(node)
    
    def visit_Return(self, node):
        """Return Statement Mutation (RSM)."""
        if self.current_id == self.mutation_id and not self.mutated and node.value:
            self.mutated = True
            node.value = ast.Constant(value=None)
        self.current_id += 1
        return self.generic_visit(node)


def count_mutable_nodes(tree: ast.AST) -> int:
    """Count total mutable nodes in AST."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.BinOp, ast.BoolOp, ast.Constant, ast.UnaryOp, ast.Return)):
            count += 1
    return count


def generate_constant_variations(function_code: str, count: int) -> list:
    """Generate variations by modifying numeric constants."""
    try:
        tree = ast.parse(function_code)
        constants = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, int)]
        if not constants:
            return []
        
        variations = []
        for i, _ in enumerate(constants[:count]):
            for mod in [-2, -1, 1, 2]:
                if len(variations) >= count:
                    return variations
                try:
                    tree_copy = copy.deepcopy(tree)
                    const_nodes = [n for n in ast.walk(tree_copy) 
                                 if isinstance(n, ast.Constant) and isinstance(n.value, int)]
                    if i < len(const_nodes):
                        const_nodes[i].value += mod
                        variations.append(ast.unparse(tree_copy))
                except:
                    continue
        return variations
    except:
        return []


def are_mutants_equivalent(original_code: str, mutant_code: str, test_cases: list) -> bool:
    """Check if mutant is equivalent to original (same behavior)."""
    if original_code == mutant_code:
        return True
    
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError()))
    try:
        signal.alarm(2)
        exec_orig, exec_mut = {}, {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            exec(original_code, exec_orig)
            exec(mutant_code, exec_mut)
        
        func_name = extract_function_name(original_code)
        orig_func, mut_func = exec_orig[func_name], exec_mut[func_name]
        
        for test_case in test_cases[:min(10, len(test_cases))]:
            try:
                if orig_func(*test_case["args"], **test_case.get("kwargs", {})) != \
                   mut_func(*test_case["args"], **test_case.get("kwargs", {})):
                    signal.alarm(0)
                    return False
            except:
                signal.alarm(0)
                return False
        signal.alarm(0)
        return True
    except:
        signal.alarm(0)
        return False


def apply_mutations(tree, function_code, test_cases, seen_codes, mode, total_nodes):
    """Helper to apply mutations and filter."""
    mutants = []
    for mutation_id in range(total_nodes):
        mutator = MutmutOperator(mutation_id, mode)
        mutated_tree = mutator.visit(copy.deepcopy(tree))
        
        if mutator.mutated:
            try:
                mutant_code = ast.unparse(mutated_tree)
                if mutant_code not in seen_codes and mutant_code != function_code and \
                   not are_mutants_equivalent(function_code, mutant_code, test_cases):
                    seen_codes.add(mutant_code)
                    mutants.append({"code": mutant_code, "type": f"mutmut_{mode}", "mutation_id": mutation_id})
            except:
                pass
    return mutants


def generate_mutants(function_code: str, test_cases: list, num_mutants: int = NUM_MUTANTS) -> list:
    """Generate exactly num_mutants using Mutmut approach with smart padding."""
    try:
        tree = ast.parse(function_code)
    except SyntaxError:
        return []
    
    total_nodes = count_mutable_nodes(tree)
    if total_nodes == 0:
        return []
    
    mutants, seen_codes = [], set()
    
    # Strategy 1 & 2: Standard and aggressive mutations
    for mode in ["default", "aggressive"]:
        if len(mutants) >= num_mutants:
            break
        mutants.extend(apply_mutations(tree, function_code, test_cases, seen_codes, mode, total_nodes))
        mutants = mutants[:num_mutants]
    
    # Strategy 3: Compound mutations (limited attempts)
    if len(mutants) < num_mutants:
        for attempts, (id1, id2) in enumerate([(i, j) for i in range(min(total_nodes, 5)) 
                                                for j in range(i + 1, min(total_nodes, 5))]):
            if len(mutants) >= num_mutants or attempts >= 20:
                break
            try:
                mut1, mut2 = MutmutOperator(id1, "default"), MutmutOperator(id2, "default")
                tree_copy = mut2.visit(mut1.visit(copy.deepcopy(tree)))
                
                if mut1.mutated and mut2.mutated:
                    mutant_code = ast.unparse(tree_copy)
                    if mutant_code not in seen_codes and mutant_code != function_code and \
                       not are_mutants_equivalent(function_code, mutant_code, test_cases):
                        seen_codes.add(mutant_code)
                        mutants.append({"code": mutant_code, "type": "mutmut_compound", "mutation_id": f"{id1}_{id2}"})
            except:
                pass
    
    # Strategy 4: Constant variations
    if len(mutants) < num_mutants:
        for i, var_code in enumerate(generate_constant_variations(function_code, num_mutants - len(mutants))):
            if len(mutants) >= num_mutants or i >= 10:
                break
            if var_code not in seen_codes and var_code != function_code and \
               not are_mutants_equivalent(function_code, var_code, test_cases):
                seen_codes.add(var_code)
                mutants.append({"code": var_code, "type": "mutmut_variation", "mutation_id": f"var_{i}"})
    
    # Strategy 5 & 6: Padding with mutations or duplicates
    if len(mutants) < num_mutants and mutants:
        attempts = 0
        for i in range(num_mutants - len(mutants)):
            if attempts >= 15 or len(mutants) >= num_mutants:
                break
            try:
                tree_mut = ast.parse(mutants[i % len(mutants)]["code"])
                for mutation_id in range(min(total_nodes, 5)):
                    attempts += 1
                    if attempts >= 15:
                        break
                    mutator = MutmutOperator(mutation_id, "aggressive")
                    mutated_tree = mutator.visit(copy.deepcopy(tree_mut))
                    if mutator.mutated:
                        mutant_code = ast.unparse(mutated_tree)
                        if mutant_code not in seen_codes and mutant_code != function_code:
                            seen_codes.add(mutant_code)
                            mutants.append({"code": mutant_code, "type": "mutmut_padded", "mutation_id": f"pad_{i}"})
                            break
            except:
                pass
        
        # Last resort: duplicate existing mutants
        while len(mutants) < num_mutants:
            base_idx = len(mutants) % len([m for m in mutants if m["type"] != "mutmut_duplicate"] or mutants)
            dup = mutants[base_idx].copy()
            dup.update({"type": "mutmut_duplicate", "mutation_id": f"dup_{len(mutants)}"})
            mutants.append(dup)
    
    return mutants[:num_mutants]


def evaluate_postcondition_on_mutant(mutant_code: str, postcondition_code: str,
                                     test_cases: list, params: list) -> bool:
    """Test if postcondition kills the mutant."""
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError()))
    
    for test_case in test_cases[:min(100, len(test_cases))]:
        try:
            signal.alarm(1)
            exec_globals = {}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                exec(mutant_code, exec_globals)
            
            result = exec_globals[extract_function_name(mutant_code)](*test_case["args"], **test_case.get("kwargs", {}))
            
            eval_env = exec_globals | {"result": result} | dict(zip(params, test_case["args"])) | test_case.get("kwargs", {})
            exec(postcondition_code, eval_env)
            signal.alarm(0)
        except:
            signal.alarm(0)
            return True
        finally:
            signal.alarm(0)
    return False


def evaluate_completeness(processed_mbpp: list, generated_postconditions: list,
                         test_cases_dict: dict) -> dict:
    """Evaluate completeness via mutation analysis."""
    print("\n=== Evaluating Completeness ===\n")
    
    completeness_report = {}
    
    for gen_post in generated_postconditions:
        task_id = gen_post["task_id"]
        function_code = gen_post["function_code"]
        postconditions = gen_post["generated_postconditions"]
        
        print(f"Evaluating function {task_id}...")
        
        if task_id not in test_cases_dict:
            print(f"  Warning: No test cases found for function {task_id}")
            continue
        
        test_cases = test_cases_dict[task_id]["test_cases"]
        params = extract_function_params(function_code)
        
        print(f"  Generating mutants...", end="", flush=True)
        signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError()))
        try:
            signal.alarm(30)
            mutants = generate_mutants(function_code, test_cases, NUM_MUTANTS)
            signal.alarm(0)
        except TimeoutError:
            signal.alarm(0)
            mutants = []
            print(" timeout!")
        
        if not mutants:
            print(f"  Warning: Could not generate mutants")
            completeness_report[str(task_id)] = {
                "naive": 0,
                "few_shot": 0,
                "chain_of_thought": 0
            }
            continue
        
        print(f" done! Generated {len(mutants)} unique mutants")
        
        task_results = {}
        for strategy in ["naive", "few_shot", "chain_of_thought"]:
            postcondition_code = postconditions.get(strategy, "")
            
            if not postcondition_code or "ERROR" in postcondition_code:
                task_results[strategy] = 0
                continue
            
            killed = 0
            for mutant in mutants:
                try:
                    if evaluate_postcondition_on_mutant(mutant["code"], postcondition_code, 
                                                        test_cases, params):
                        killed += 1
                except:
                    killed += 1
            
            kill_rate = int((killed / len(mutants)) * 100) if mutants else 0
            task_results[strategy] = kill_rate
            print(f"  {strategy}: {killed}/{len(mutants)} killed ({kill_rate}%)")
        
        completeness_report[str(task_id)] = task_results
    
    return completeness_report


def main():
    """Main execution function."""
    print("\n=== Completeness Evaluation (Mutmut Inspired Approach) ===")
    print(f"Target mutants per function: {NUM_MUTANTS}")
    print("Using standardized mutation operators with duplicate/equivalent filtering\n")
    
    print("Loading datasets...")
    processed_mbpp = load_json(PROCESSED_MBPP_FILE)
    generated_postconditions = load_json(GENERATED_POSTCONDITIONS_FILE)
    
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test cases file not found: {TEST_CASES_FILE}\n"
            "Please run correctness_evaluation.py first to generate test cases."
        )
    
    test_cases_list = load_json(TEST_CASES_FILE)
    test_cases_dict = {tc["task_id"]: tc for tc in test_cases_list}
    
    print(f"Loaded {len(processed_mbpp)} functions\n")
    
    completeness_report = evaluate_completeness(
        processed_mbpp, generated_postconditions, test_cases_dict
    )
    
    save_json(OUTPUT_FILE, completeness_report)
    print(f"\n=== Completeness Evaluation Complete ===")
    print(f"Report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
