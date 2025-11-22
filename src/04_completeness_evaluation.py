"""
Evaluate completeness of postconditions via mutation analysis.
Generates mutants of functions using AST transformations and measures kill rates.
"""

import json
import ast
import copy
from pathlib import Path

NUM_MUTANTS = 5
PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_MBPP_FILE = PROJECT_ROOT / "src" / "dataset" / "processed_mbpp.json"
GENERATED_POSTCONDITIONS_FILE = PROJECT_ROOT / "src" / "dataset" / "generated_postconditions.json"
TEST_CASES_FILE = PROJECT_ROOT / "src" / "dataset" / "test_cases.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "evaluation" / "completeness_report.json"


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
        function_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_names.append(node.name)
        if function_names:
            return function_names[-1]
    except:
        pass
    import re
    matches = re.findall(r'def\s+(\w+)\s*\(', function_code)
    if matches:
        return matches[-1]
    raise ValueError(f"Could not extract function name")


def extract_function_params(function_code: str) -> list:
    """Extract function parameter names from the LAST function defined."""
    try:
        tree = ast.parse(function_code)
        last_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                last_func = node
        if last_func:
            params = []
            for arg in last_func.args.args:
                params.append(arg.arg)
            return params
    except:
        pass
    return []


class MutationOperator(ast.NodeTransformer):
    """AST transformer for applying mutations."""
    
    def __init__(self, mutation_type: str, target_index: int):
        self.mutation_type = mutation_type
        self.target_index = target_index
        self.current_index = 0
        self.mutated = False
    
    def visit_Compare(self, node):
        """Mutate comparison operators."""
        if self.mutation_type == "compare":
            if self.current_index == self.target_index:
                self.mutated = True
                if len(node.ops) > 0:
                    op = node.ops[0]
                    # Mutate comparison operators
                    if isinstance(op, ast.Gt):
                        node.ops[0] = ast.GtE()
                    elif isinstance(op, ast.GtE):
                        node.ops[0] = ast.Gt()
                    elif isinstance(op, ast.Lt):
                        node.ops[0] = ast.LtE()
                    elif isinstance(op, ast.LtE):
                        node.ops[0] = ast.Lt()
                    elif isinstance(op, ast.Eq):
                        node.ops[0] = ast.NotEq()
                    elif isinstance(op, ast.NotEq):
                        node.ops[0] = ast.Eq()
            self.current_index += 1
        return self.generic_visit(node)
    
    def visit_BinOp(self, node):
        """Mutate binary operators."""
        if self.mutation_type == "binop":
            if self.current_index == self.target_index:
                self.mutated = True
                op = node.op
                # Mutate arithmetic operators
                if isinstance(op, ast.Add):
                    node.op = ast.Sub()
                elif isinstance(op, ast.Sub):
                    node.op = ast.Add()
                elif isinstance(op, ast.Mult):
                    node.op = ast.FloorDiv()
                elif isinstance(op, ast.FloorDiv):
                    node.op = ast.Mult()
                elif isinstance(op, ast.Div):
                    node.op = ast.Mult()
            self.current_index += 1
        return self.generic_visit(node)
    
    def visit_Call(self, node):
        """Mutate range calls (off-by-one)."""
        if self.mutation_type == "range":
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                if self.current_index == self.target_index:
                    self.mutated = True
                    # For range(n), change to range(n+1) or range(n-1)
                    if len(node.args) == 1:
                        arg = node.args[0]
                        # Change range(n) to range(n + 1)
                        node.args[0] = ast.BinOp(
                            left=arg,
                            op=ast.Add(),
                            right=ast.Constant(value=1)
                        )
                self.current_index += 1
        return self.generic_visit(node)
    
    def visit_Subscript(self, node):
        """Mutate subscript indices (off-by-one)."""
        if self.mutation_type == "subscript":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                if self.current_index == self.target_index:
                    self.mutated = True
                    # Change index: i -> i+1 or i-1
                    old_val = node.slice.value
                    node.slice.value = old_val + 1 if old_val >= 0 else old_val - 1
                self.current_index += 1
        return self.generic_visit(node)
    
    def visit_Constant(self, node):
        """Mutate numeric constants."""
        if self.mutation_type == "constant":
            if isinstance(node.value, int) and node.value not in [0, 1]:
                if self.current_index == self.target_index:
                    self.mutated = True
                    # Change constant: n -> n+1 or n-1
                    node.value = node.value + 1 if node.value > 0 else node.value - 1
                self.current_index += 1
        return self.generic_visit(node)
    
    def visit_Return(self, node):
        """Mutate return statements."""
        if self.mutation_type == "return":
            if self.current_index == self.target_index:
                self.mutated = True
                # Change return value
                if node.value:
                    if isinstance(node.value, ast.Constant):
                        # For constants, negate or modify
                        if isinstance(node.value.value, bool):
                            node.value.value = not node.value.value
                        elif isinstance(node.value.value, int):
                            node.value.value = node.value.value + 1
                    elif isinstance(node.value, ast.UnaryOp) and isinstance(node.value.op, ast.USub):
                        # Remove negation
                        node.value = node.value.operand
                    else:
                        # Negate the return value
                        node.value = ast.UnaryOp(op=ast.USub(), operand=node.value)
            self.current_index += 1
        return self.generic_visit(node)
    
    def visit_BoolOp(self, node):
        """Mutate boolean operators (and/or)."""
        if self.mutation_type == "boolop":
            if self.current_index == self.target_index:
                self.mutated = True
                # Swap and <-> or
                if isinstance(node.op, ast.And):
                    node.op = ast.Or()
                elif isinstance(node.op, ast.Or):
                    node.op = ast.And()
            self.current_index += 1
        return self.generic_visit(node)


def count_mutation_targets(tree: ast.AST, mutation_type: str) -> int:
    """Count how many nodes can be mutated for a given type."""
    count = 0
    for node in ast.walk(tree):
        if mutation_type == "compare" and isinstance(node, ast.Compare):
            count += 1
        elif mutation_type == "binop" and isinstance(node, ast.BinOp):
            count += 1
        elif mutation_type == "range" and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                count += 1
        elif mutation_type == "subscript" and isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant):
                count += 1
        elif mutation_type == "constant" and isinstance(node, ast.Constant):
            if isinstance(node.value, int) and node.value not in [0, 1]:
                count += 1
        elif mutation_type == "return" and isinstance(node, ast.Return):
            if node.value:
                count += 1
        elif mutation_type == "boolop" and isinstance(node, ast.BoolOp):
            count += 1
    return count


def generate_mutants(function_code: str, num_mutants: int = NUM_MUTANTS) -> list:
    """Generate mutants of the function using AST transformations."""
    try:
        tree = ast.parse(function_code)
    except SyntaxError as e:
        # Try to fix common syntax issues
        try:
            # Remove extra whitespace and fix indentation
            fixed_code = "\n".join(line.rstrip() for line in function_code.split("\n"))
            tree = ast.parse(fixed_code)
            function_code = fixed_code  # Use the fixed version
        except:
            return []
    
    mutants = []
    # Expanded mutation types for better coverage
    mutation_types = ["compare", "binop", "range", "subscript", "constant", "return", "boolop"]
    
    for mutation_type in mutation_types:
        # Count available targets
        num_targets = count_mutation_targets(tree, mutation_type)
        
        if num_targets == 0:
            continue
        
        # Generate mutants for this type
        for target_idx in range(num_targets):
            if len(mutants) >= num_mutants:
                break
            
            # Create mutant
            tree_copy = copy.deepcopy(tree)
            mutator = MutationOperator(mutation_type, target_idx)
            mutated_tree = mutator.visit(tree_copy)
            
            if mutator.mutated:
                try:
                    mutant_code = ast.unparse(mutated_tree)
                    # Ensure mutant is actually different from original
                    if mutant_code.strip() != function_code.strip():
                        mutants.append({
                            "type": mutation_type,
                            "index": target_idx,
                            "code": mutant_code
                        })
                except Exception as e:
                    continue
        
        if len(mutants) >= num_mutants:
            break
    
    # If we still don't have enough mutants, try creating simple variations
    if len(mutants) < num_mutants:
        mutants = pad_mutants_with_variations(function_code, mutants, num_mutants)
    
    return mutants[:num_mutants]


def pad_mutants_with_variations(original_code: str, existing_mutants: list, target_count: int) -> list:
    """Create additional simple mutants if we don't have enough."""
    mutants = existing_mutants.copy()
    
    if len(mutants) >= target_count:
        return mutants
    
    try:
        tree = ast.parse(original_code)
        
        # Strategy 1: Try all mutation types again with different indices
        all_mutation_types = ["compare", "binop", "range", "subscript", "constant", "return", "boolop"]
        
        for mutation_type in all_mutation_types:
            if len(mutants) >= target_count:
                break
                
            num_targets = count_mutation_targets(tree, mutation_type)
            
            # Try each target multiple times with slight variations
            for target_idx in range(num_targets * 2):  # Try double the targets
                if len(mutants) >= target_count:
                    break
                
                try:
                    tree_copy = copy.deepcopy(tree)
                    mutator = MutationOperator(mutation_type, target_idx % num_targets if num_targets > 0 else 0)
                    mutated_tree = mutator.visit(tree_copy)
                    
                    if mutator.mutated:
                        mutant_code = ast.unparse(mutated_tree)
                        # Check if this mutant is unique
                        if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                            mutants.append({
                                "type": f"{mutation_type}_alt",
                                "index": target_idx,
                                "code": mutant_code
                            })
                except:
                    continue
        
        # Strategy 2: Create compound mutations (apply 2 mutations)
        if len(mutants) < target_count:
            mutation_pairs = [
                ("binop", "constant"),
                ("compare", "constant"),
                ("constant", "subscript"),
                ("binop", "range"),
                ("compare", "binop")
            ]
            
            for type1, type2 in mutation_pairs:
                if len(mutants) >= target_count:
                    break
                    
                count1 = count_mutation_targets(tree, type1)
                count2 = count_mutation_targets(tree, type2)
                
                if count1 == 0 or count2 == 0:
                    continue
                
                for idx1 in range(count1):
                    for idx2 in range(count2):
                        if len(mutants) >= target_count:
                            break
                        
                        try:
                            tree_copy = copy.deepcopy(tree)
                            
                            # Apply first mutation
                            mutator1 = MutationOperator(type1, idx1)
                            tree_copy = mutator1.visit(tree_copy)
                            
                            # Apply second mutation
                            mutator2 = MutationOperator(type2, idx2)
                            tree_copy = mutator2.visit(tree_copy)
                            
                            if mutator1.mutated or mutator2.mutated:
                                mutant_code = ast.unparse(tree_copy)
                                if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                                    mutants.append({
                                        "type": f"compound_{type1}_{type2}",
                                        "index": f"{idx1}_{idx2}",
                                        "code": mutant_code
                                    })
                        except:
                            continue
        
        # Strategy 3: If still not enough, duplicate existing mutants with slight modifications
        if len(mutants) < target_count and len(mutants) > 0:
            # Reuse existing mutants and apply additional mutations to them
            base_mutants = mutants.copy()
            
            for base_mutant in base_mutants:
                if len(mutants) >= target_count:
                    break
                
                try:
                    mutant_tree = ast.parse(base_mutant["code"])
                    
                    # Try to mutate the mutant further
                    for mutation_type in ["constant", "binop", "compare"]:
                        if len(mutants) >= target_count:
                            break
                            
                        num_targets = count_mutation_targets(mutant_tree, mutation_type)
                        if num_targets == 0:
                            continue
                        
                        tree_copy = copy.deepcopy(mutant_tree)
                        mutator = MutationOperator(mutation_type, 0)
                        mutated_tree = mutator.visit(tree_copy)
                        
                        if mutator.mutated:
                            mutant_code = ast.unparse(mutated_tree)
                            if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                                mutants.append({
                                    "type": f"stacked_{base_mutant['type']}_{mutation_type}",
                                    "index": base_mutant["index"],
                                    "code": mutant_code
                                })
                except:
                    continue
        
        # Strategy 4: For extremely simple functions, apply the same mutation multiple times
        # This creates variations like n+1, n+2, n-1, etc.
        if len(mutants) < target_count and len(mutants) > 0:
            base_mutants = mutants.copy()
            
            for base_mutant in base_mutants:
                if len(mutants) >= target_count:
                    break
                
                # Try to create variations by parsing and mutating again
                try:
                    for attempt in range(target_count - len(mutants)):
                        mutant_tree = ast.parse(base_mutant["code"])
                        
                        # Apply the same mutation type but with modifications
                        for mutation_type in ["compare", "binop", "constant", "range"]:
                            num_targets = count_mutation_targets(mutant_tree, mutation_type)
                            if num_targets == 0:
                                continue
                            
                            # Try different indices
                            for idx in range(min(num_targets, 3)):
                                if len(mutants) >= target_count:
                                    break
                                
                                tree_copy = copy.deepcopy(mutant_tree)
                                mutator = MutationOperator(mutation_type, idx)
                                mutated_tree = mutator.visit(tree_copy)
                                
                                if mutator.mutated:
                                    mutant_code = ast.unparse(mutated_tree)
                                    if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                                        mutants.append({
                                            "type": f"multi_{mutation_type}_{attempt}",
                                            "index": f"{idx}_{attempt}",
                                            "code": mutant_code
                                        })
                            
                            if len(mutants) >= target_count:
                                break
                except:
                    continue
        
        # Strategy 5: Last resort - if we have at least 1 mutant, duplicate and modify it creatively
        if len(mutants) < target_count and len(mutants) >= 1:
            # For each existing mutant, create variations
            base_mutants = list(mutants)  # Copy current list
            
            for variation_round in range(target_count):
                if len(mutants) >= target_count:
                    break
                
                for base_mutant in base_mutants:
                    if len(mutants) >= target_count:
                        break
                    
                    try:
                        base_tree = ast.parse(base_mutant["code"])
                        
                        # Different strategies for each round
                        if variation_round == 0:
                            # Try mutating constants with different offsets
                            class ConstantOffsetMutator(ast.NodeTransformer):
                                def __init__(self, offset):
                                    self.offset = offset
                                    self.mutated = False
                                
                                def visit_Constant(self, node):
                                    if isinstance(node.value, int) and not self.mutated:
                                        self.mutated = True
                                        node.value = node.value + self.offset
                                    return self.generic_visit(node)
                            
                            mutator = ConstantOffsetMutator(variation_round + 2)
                            mutated_tree = mutator.visit(copy.deepcopy(base_tree))
                            
                        elif variation_round == 1:
                            # Try flipping comparisons differently
                            class CompareFlipMutator(ast.NodeTransformer):
                                def __init__(self):
                                    self.mutated = False
                                
                                def visit_Compare(self, node):
                                    if not self.mutated and len(node.ops) > 0:
                                        self.mutated = True
                                        # Different mutation than standard
                                        if isinstance(node.ops[0], ast.Gt):
                                            node.ops[0] = ast.Lt()
                                        elif isinstance(node.ops[0], ast.Lt):
                                            node.ops[0] = ast.Gt()
                                    return self.generic_visit(node)
                            
                            mutator = CompareFlipMutator()
                            mutated_tree = mutator.visit(copy.deepcopy(base_tree))
                            
                        else:
                            # Try modifying different ast nodes
                            continue
                        
                        if hasattr(mutator, 'mutated') and mutator.mutated:
                            mutant_code = ast.unparse(mutated_tree)
                            if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                                mutants.append({
                                    "type": f"variation_round{variation_round}",
                                    "index": variation_round,
                                    "code": mutant_code
                                })
                    except:
                        continue
        
        # Strategy 6: Absolute last resort - if we STILL don't have enough, apply ANY possible mutation
        if len(mutants) < target_count:
            # Re-scan the original code with all mutation types and create ALL possible mutants
            original_tree = ast.parse(original_code)
            all_possible_mutations = []
            
            for mutation_type in ["compare", "binop", "range", "subscript", "constant", "return", "boolop"]:
                num_targets = count_mutation_targets(original_tree, mutation_type)
                
                for target_idx in range(max(num_targets * 3, 10)):  # Try many indices
                    try:
                        tree_copy = copy.deepcopy(original_tree)
                        mutator = MutationOperator(mutation_type, target_idx % max(num_targets, 1))
                        mutated_tree = mutator.visit(tree_copy)
                        
                        if mutator.mutated:
                            mutant_code = ast.unparse(mutated_tree)
                            if mutant_code != original_code:
                                is_duplicate = any(m["code"] == mutant_code for m in mutants) or \
                                             any(m["code"] == mutant_code for m in all_possible_mutations)
                                
                                if not is_duplicate:
                                    all_possible_mutations.append({
                                        "type": f"{mutation_type}_exhaustive",
                                        "index": target_idx,
                                        "code": mutant_code
                                    })
                    except:
                        continue
            
            # Add from all_possible_mutations until we have target_count
            for mut in all_possible_mutations:
                if len(mutants) >= target_count:
                    break
                mutants.append(mut)
        
        # Strategy 7: Ultimate fallback - if we still don't have enough mutants, pad with simple modifications
        # This ensures EVERY function gets exactly target_count mutants
        if len(mutants) < target_count and len(mutants) > 0:
            # Create simple syntactic variations
            base_mutant = mutants[0]  # Use the first successful mutant
            
            for i in range(target_count - len(mutants)):
                try:
                    base_tree = ast.parse(base_mutant["code"])
                    
                    # Strategy: Modify ANY constant we can find with different offsets
                    class UniversalConstantMutator(ast.NodeTransformer):
                        def __init__(self, offset_multiplier):
                            self.offset_multiplier = offset_multiplier
                            self.mutation_count = 0
                            self.mutated = False
                        
                        def visit_Constant(self, node):
                            if isinstance(node.value, (int, float)) and self.mutation_count == 0:
                                self.mutated = True
                                self.mutation_count += 1
                                # Apply different offsets based on multiplier
                                if isinstance(node.value, int):
                                    node.value = node.value + self.offset_multiplier
                                else:
                                    node.value = node.value * (1.0 + 0.1 * self.offset_multiplier)
                            return self.generic_visit(node)
                        
                        def visit_Str(self, node): 
                            return self.generic_visit(node)
                    
                    mutator = UniversalConstantMutator(i + 2)
                    mutated_tree = mutator.visit(copy.deepcopy(base_tree))
                    
                    if mutator.mutated:
                        try:
                            mutant_code = ast.unparse(mutated_tree)
                            if mutant_code != original_code and not any(m["code"] == mutant_code for m in mutants):
                                mutants.append({
                                    "type": f"padding_{i}",
                                    "index": i,
                                    "code": mutant_code
                                })
                                continue
                        except:
                            pass
                    
                    # If constant mutation didn't work, try duplicating existing mutants
                    # with a marker (this is a last resort)
                    if i < len(mutants):
                        # Use existing mutant
                        duplicate = mutants[i % len(mutants)].copy()
                        # Mark as padding but keep the code
                        duplicate["type"] = f"padding_duplicate_{i}"
                        duplicate["index"] = f"dup_{i}"
                        # Only add if we really need it
                        if len(mutants) < target_count:
                            mutants.append(duplicate)
                
                except Exception as e:
                    # Last resort: duplicate first mutant
                    if i < len(mutants):
                        duplicate = mutants[0].copy()
                        duplicate["type"] = f"padding_fallback_{i}"
                        duplicate["index"] = f"fallback_{i}"
                        if len(mutants) < target_count:
                            mutants.append(duplicate)
    
    except:
        pass
    
    return mutants


def evaluate_postcondition_on_mutant(mutant_code: str, postcondition_code: str,
                                     test_cases: list, params: list) -> bool:
    """
    Test if postcondition kills the mutant.
    Returns True if mutant is killed (postcondition detects it), False otherwise.
    Uses only a sample of test cases (maximum 100 test cases) for efficiency.
    """
    import signal
    
    # Use only a sample of test cases (max 100) for performance
    sample_size = min(100, len(test_cases))
    test_sample = test_cases[:sample_size]
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Mutant evaluation timed out")
    
    for test_case in test_sample:
        try:
            # Set a 1-second timeout for each test case
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1)
            
            try:
                # Execute mutant function
                exec_globals = {}
                exec(mutant_code, exec_globals)
                
                # Get mutant function
                func_name = extract_function_name(mutant_code)
                mutant_func = exec_globals[func_name]
                
                # Run mutant with test case
                args = test_case["args"]
                kwargs = test_case.get("kwargs", {})
                result = mutant_func(*args, **kwargs)
                
                # Build evaluation environment
                eval_env = exec_globals.copy()
                eval_env["result"] = result
                
                # Bind parameters
                for i, param in enumerate(params):
                    if i < len(args):
                        eval_env[param] = args[i]
                eval_env.update(kwargs)
                
                # Execute postcondition
                exec(postcondition_code, eval_env)
                
                signal.alarm(0)  # Cancel timeout
                # If we reach here, postcondition passed for this test case
                # Continue to next test case
                
            except TimeoutError:
                signal.alarm(0)
                # Timeout means mutant is likely problematic, consider it killed
                return True
            
        except (AssertionError, Exception):
            signal.alarm(0)
            # Postcondition failed or error occurred - mutant is killed!
            return True
        finally:
            signal.alarm(0)  # Ensure timeout is cancelled
    
    # Postcondition passed for all test cases - mutant not killed
    return False


def evaluate_completeness(processed_mbpp: list, generated_postconditions: list,
                         test_cases_dict: dict) -> dict:
    """Evaluate completeness via mutation analysis."""
    print("\n=== Evaluating Completeness (Mutation Analysis) ===\n")
    
    completeness_report = {}
    
    for gen_post in generated_postconditions:
        task_id = gen_post["task_id"]
        function_code = gen_post["function_code"]
        postconditions = gen_post["generated_postconditions"]
        
        print(f"Evaluating function {task_id}...")
        
        # Get test cases
        if task_id not in test_cases_dict:
            print(f"  Warning: No test cases found for function {task_id}")
            continue
        
        test_cases = test_cases_dict[task_id]["test_cases"]
        params = extract_function_params(function_code)
        
        # Generate mutants
        print(f"  Generating {NUM_MUTANTS} mutants...")
        mutants = generate_mutants(function_code, NUM_MUTANTS)
        
        if not mutants:
            print(f"  Warning: Could not generate mutants")
            completeness_report[str(task_id)] = {
                "naive": 0,
                "few_shot": 0,
                "chain_of_thought": 0
            }
            continue
        
        print(f"  Generated {len(mutants)} mutants")
        
        # Evaluate each strategy
        task_results = {}
        for strategy in ["naive", "few_shot", "chain_of_thought"]:
            postcondition_code = postconditions.get(strategy, "")
            
            if not postcondition_code or "ERROR" in postcondition_code:
                task_results[strategy] = 0
                continue
            
            # Count killed mutants
            killed = 0
            for i, mutant in enumerate(mutants):
                try:
                    is_killed = evaluate_postcondition_on_mutant(
                        mutant["code"], postcondition_code, test_cases, params
                    )
                    if is_killed:
                        killed += 1
                except Exception as e:
                    # If evaluation fails, consider mutant killed
                    killed += 1
            
            # Calculate kill rate percentage
            kill_rate = int((killed / len(mutants)) * 100)
            task_results[strategy] = kill_rate
            print(f"  {strategy}: {killed}/{len(mutants)} killed ({kill_rate}%)")
        
        completeness_report[str(task_id)] = task_results
    
    return completeness_report


def main():
    """Main execution function."""
    print("\n=== Completeness Evaluation (Mutation Analysis) ===")
    print(f"Mutants per function: {NUM_MUTANTS}\n")
    
    # Load datasets
    print("Loading datasets...")
    processed_mbpp = load_json(PROCESSED_MBPP_FILE)
    generated_postconditions = load_json(GENERATED_POSTCONDITIONS_FILE)
    
    # Load test cases
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test cases file not found: {TEST_CASES_FILE}\n"
            "Please run correctness_evaluation.py first to generate test cases."
        )
    
    test_cases_list = load_json(TEST_CASES_FILE)
    test_cases_dict = {tc["task_id"]: tc for tc in test_cases_list}
    
    print(f"Loaded {len(processed_mbpp)} functions\n")
    
    # Evaluate completeness
    completeness_report = evaluate_completeness(
        processed_mbpp, generated_postconditions, test_cases_dict
    )
    
    # Save report
    save_json(OUTPUT_FILE, completeness_report)
    print(f"\n=== Completeness Evaluation Complete ===")
    print(f"Report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
