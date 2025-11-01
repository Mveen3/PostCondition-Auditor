import json
import os
import time  # We'll add a small delay to be kind to the API
import inspect  # For introspecting function signatures
import re  # For cleaning up code strings

# Import the function we already built to call the LLM
try:
    from llm_client import get_llm_response
except ImportError:
    print("Error: llm_client.py not found or get_llm_response function is missing.")
    exit()

INPUT_FILE = "input_50_functions.json"
OUTPUT_FILE = "generated_postconditions.json"  # Our final deliverable

# --- Helper Functions (Loading & Prompts) ---

def load_functions(input_file):
    """Loads the 50 functions from our curated JSON file."""
    try:
        with open(input_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_file}")
        return None


def get_function_params(function_code: str) -> str:
    """
    Parses the function code to get its parameter names.
    e.g., "def my_func(a, b):" -> "a, b"
    """
    try:
        # Clean up code string if it's nested
        function_code = inspect.cleandoc(function_code)
        
        # Define a temporary function to parse
        temp_func_def = {}
        exec(function_code, globals(), temp_func_def)
        
        # Find the first function defined in the exec
        func_name = [k for k in temp_func_def if callable(temp_func_def[k])][0]
        func_obj = temp_func_def[func_name]
        
        # Get parameter names
        params = inspect.signature(func_obj).parameters
        return ", ".join(params.keys())
    except Exception as e:
        print(f"  - WARNING: Could not parse params for code. Error: {e}")
        return ""


def generate_naive_prompt(function_code: str) -> str:
    """
    Generates a strict, zero-shot prompt demanding a
    runnable Python assertion.
    """
    param_names = get_function_params(function_code)
    
    prompt = f"""
You are an automated test assertion generator.
Your task is to generate a single-line Python boolean expression
that formally verifies the postcondition of the given function.

The Python expression must:
1. Use the exact variable name `result` to represent the return value.
2. Use the function's original parameter names: `{param_names}`.
3. Evaluate to `True` if the postcondition is met, and `False` otherwise.
4. Be a single line of valid Python code.
5. Contain NO natural language or explanations.

Function:
```python
{function_code}
```

Single-Line Python Assertion:
"""
    return prompt


def generate_few_shot_prompt(function_code: str) -> str:
    """
    Generates a few-shot prompt demanding a
    runnable Python assertion, with code examples.
    """
    param_names = get_function_params(function_code)
    
    examples = """
--- Example 1 ---
Function:
```python
def add(a, b):
    return a + b
```
Single-Line Python Assertion:
result == a + b

--- Example 2 ---
Function:
```python
def find_max(numbers):
    return max(numbers)
```
Single-Line Python Assertion:
all(result >= x for x in numbers) and result in numbers

--- Example 3 ---
Function:
```python
def is_even(n):
    return n % 2 == 0
```
Single-Line Python Assertion:
(n % 2 == 0) == result
"""
    
    prompt = f"""
You are an automated test assertion generator.
Follow the format of the examples provided.

The Python expression must:
1. Use the exact variable name `result` to represent the return value.
2. Use the function's original parameter names: `{param_names}`.
3. Evaluate to `True` if the postcondition is met, and `False` otherwise.
4. Be a single line of valid Python code.
5. Contain NO natural language or explanations.

{examples}

--- Task ---
Function:
```python
{function_code}
```

Single-Line Python Assertion:
"""
    return prompt


def generate_cot_prompt(function_code: str) -> str:
    """
    Generates a Chain-of-Thought (CoT) prompt, instructing
    the LLM to reason first, then provide a runnable assertion.
    """
    param_names = get_function_params(function_code)
    
    prompt = f"""
You must perform two steps for the function below.

Function:
```python
{function_code}
```

Step 1: Provide a step-by-step reasoning about this function's purpose, inputs, outputs, and edge cases.
Step 2: Based only on your reasoning, write a single-line Python boolean assertion that verifies the postcondition.

The Python expression must:
1. Use the exact variable name `result` to represent the return value.
2. Use the function's original parameter names: `{param_names}`.
3. Evaluate to `True` if the postcondition is met, and `False` otherwise.
4. Be a single line of valid Python code.

Use the following format for your response:

Reasoning: [Your detailed reasoning here]

Assertion: [Your single-line Python assertion here]
"""
    return prompt


# --- NEW Parser Functions ---

def parse_code_response(response: str) -> str:
    """
    Parses a direct code response.
    It strips markdown fences (```) and whitespace.
    """
    # Use regex to find code between ```python and ```, or just ``` and ```
    # THE FIX: We need to look for the opening ``` *before*
    # the optional (?:python\n) part.
    match = re.search(r'```(?:python\n)?(.*?)```', response, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # If no markdown, just strip whitespace
    return response.strip()


def parse_cot_response(response: str) -> str:
    """
    Parses the CoT response, extracting only the text
    after 'Assertion:'.
    """
    keyword = "Assertion:"
    if keyword in response:
        # Split at the last "Assertion:" and take what's after it
        assertion_part = response.rsplit(keyword, 1)[1]
        # Then, clean it using the code parser
        return parse_code_response(assertion_part)
    # Fallback if the LLM failed to provide the keyword
    print(f"  - WARNING: CoT response missing 'Assertion:' keyword.")
    return ""  # Return empty string to signify a failed generation


# --- FINAL Main Function ---

def main():
    """
    Main function for the Prompting Strategy Engine.
    This will now:
    1. Loop through all 50 functions.
    2. Call all 3 *new* prompt strategies for each.
    3. Parse the responses to get clean code assertions.
    4. Save the final results to 'generated_postconditions.json'.
    """
    print(f"Starting Prompt Engine... Will save results to {OUTPUT_FILE}")

    functions = load_functions(INPUT_FILE)

    if not functions:
        print(f"No functions loaded from {INPUT_FILE}. Exiting.")
        return

    print(f"Successfully loaded {len(functions)} functions.")

    all_results = []

    # Loop through ALL functions
    for i, func in enumerate(functions, 1):
        func_code = func.get('code')
        task_id = func.get('task_id')
        
        print(f"\n--- Processing Task {i}/{len(functions)} (ID: {task_id}) ---")

        # --- Strategy 1: Naive Prompt ---
        print("  - Generating Naive Prompt...")
        naive_prompt_string = generate_naive_prompt(func_code)
        raw_naive = get_llm_response(naive_prompt_string)
        parsed_naive = parse_code_response(raw_naive)
        
        time.sleep(2)  # 2-second delay to respect API rate limits
        
        # --- Strategy 2: Few-Shot Prompt ---
        print("  - Generating Few-Shot Prompt...")
        few_shot_prompt_string = generate_few_shot_prompt(func_code)
        raw_few_shot = get_llm_response(few_shot_prompt_string)
        parsed_few_shot = parse_code_response(raw_few_shot)
        
        time.sleep(2)  # 2-second delay

        # --- Strategy 3: Chain-of-Thought (CoT) Prompt ---
        print("  - Generating CoT Prompt...")
        cot_prompt_string = generate_cot_prompt(func_code)
        raw_cot = get_llm_response(cot_prompt_string)
        parsed_cot = parse_cot_response(raw_cot)
        
        # --- Store the CLEAN, PARSED results ---
        result_data = {
            "task_id": task_id,
            "function_code": func_code,
            "generated_postconditions": {
                "naive": parsed_naive,
                "few_shot": parsed_few_shot,
                "cot": parsed_cot
            }
        }
        all_results.append(result_data)
        
        time.sleep(2)  # 2-second delay

    # --- Save all results to our output file ---
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\n--- ALL TASKS COMPLETE ---")
        print(f"Successfully saved {len(all_results)} results to {OUTPUT_FILE}")
    except Exception as e:
        print(f"\n--- ERROR: Failed to save results ---")
        print(e)


if __name__ == "__main__":
    main()