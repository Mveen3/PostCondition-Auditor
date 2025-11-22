"""
Generate postconditions for MBPP functions using Gemini 2.5 Flash.
Uses three prompting strategies: naive, few_shot, and chain_of_thought.
"""

import google.generativeai as genai
import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration ---
MODEL_NAME = "gemini-2.5-flash"
API_CALL_DELAY_SECONDS = 1
MAX_RETRIES = 3

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_FILE = PROJECT_ROOT / "src" / "dataset" / "processed_mbpp.json"
OUTPUT_FILE = PROJECT_ROOT / "src" / "dataset" / "generated_postconditions.json"


def load_api_key():
    """Load the Gemini API key from .env file.
    """
    load_dotenv(override=True)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in .env file. "
            "Please set GEMINI_API_KEY in your .env file."
        )
    return api_key


def configure_gemini():
    """Configure the Gemini API client with fresh API key.
    
    Loads the API key dynamically each time, allows switching
    between different API keys by editing .env without restarting Docker.
    """
    api_key = load_api_key()
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def create_naive_prompt(prompt: str, function_code: str) -> str:
    """Creates a direct, zero-shot prompt."""
    return f"""Given the following Python function and its description, generate a single Python postcondition assertion.

Function description: {prompt}

Function code:
```python
{function_code}
```

A postcondition is an assertion that must be true after the function executes successfully.

Requirements:
1. Use 'result' to refer to the function's return value
2. Use the function's parameter names as they appear in the signature
3. Use only Python built-ins like len, all, any, sorted, range, min, max, sum, abs, set, list, tuple, dict, enumerate, zip
4. Write a single assert statement or a simple boolean expression
5. Do not reference undefined variables or globals

Provide only the postcondition code in your response, wrapped in <postcondition> tags.

Example format:
<postcondition>assert len(result) == len(input_list)</postcondition>

Now generate the postcondition:"""


def create_few_shot_prompt(prompt: str, function_code: str) -> str:
    """Creates a prompt with hand-curated examples."""
    examples = """Here are examples of functions with their correct postconditions:

Example 1:
Function: Add two numbers
```python
def add_numbers(a, b):
    return a + b
```
Postcondition:
<postcondition>assert result == a + b</postcondition>

Example 2:
Function: Find maximum in a list
```python
def find_max(numbers):
    if not numbers:
        return None
    return max(numbers)
```
Postcondition:
<postcondition>assert (result is None and len(numbers) == 0) or (result in numbers and all(result >= x for x in numbers))</postcondition>

Example 3:
Function: Square all elements in a list
```python
def square_list(numbers):
    return [x * x for x in numbers]
```
Postcondition:
<postcondition>assert len(result) == len(numbers) and all(result[i] == numbers[i]**2 for i in range(len(numbers)))</postcondition>

"""
    return f"""{examples}

Now, generate a postcondition for this function following the same pattern:

Function description: {prompt}

Function code:
```python
{function_code}
```

Requirements:
1. Use 'result' to refer to the function's return value
2. Use the function's parameter names as they appear in the signature
3. Use only Python built-ins like len, all, any, sorted, range, min, max, sum, abs, set, list, tuple, dict, enumerate, zip
4. Write a single assert statement
5. Do not reference undefined variables or globals

Provide only the postcondition code wrapped in <postcondition> tags:"""


def create_cot_prompt(prompt: str, function_code: str) -> str:
    """Creates a Chain-of-Thought prompt."""
    return f"""You are a software verification expert. Analyze this function step-by-step and generate a postcondition.

Function description: {prompt}

Function code:
```python
{function_code}
```

Please think through this systematically:

1. UNDERSTAND: What does this function do? What are its inputs and expected output?

2. IDENTIFY INVARIANTS: What properties must always hold true after execution?
   - Type constraints (e.g., return type)
   - Size/length relationships
   - Value constraints
   - Relationships between input and output

3. CONSIDER EDGE CASES: What special cases need handling?
   - Empty inputs
   - Single element inputs
   - Boundary conditions

4. FORMULATE POSTCONDITION: Based on the above analysis, write a single Python assert statement.

Requirements for the postcondition:
- Use 'result' to refer to the return value
- Use parameter names from the function signature
- Use only Python built-ins (len, all, any, sorted, range, min, max, sum, abs, set, list, tuple, dict, enumerate, zip)
- Do not reference undefined variables

After your analysis, provide the final postcondition wrapped in <postcondition> tags.

Example:
<postcondition>assert len(result) == len(input_param)</postcondition>"""


def extract_postcondition(response_text: str) -> str:
    """Extract postcondition from LLM response."""
    # Try to find content within <postcondition> tags
    match = re.search(r'<postcondition>(.*?)</postcondition>', response_text, re.DOTALL)
    if match:
        postcondition = match.group(1).strip()
        # Remove markdown code blocks if present
        postcondition = re.sub(r'^```python\s*\n?', '', postcondition)
        postcondition = re.sub(r'\n?```$', '', postcondition)
        return postcondition.strip()
    
    # Fallback: look for assert statements
    lines = response_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('assert '):
            return line
    
    # Last resort: return a safe default
    return "Failed to extract postcondition"


def call_llm_with_retry(model, prompt: str, max_retries: int = MAX_RETRIES) -> str:
    """Call the LLM with retry logic."""
    for attempt in range(max_retries):
        try:
            time.sleep(API_CALL_DELAY_SECONDS)
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(API_CALL_DELAY_SECONDS * 2)
    
    return "ERROR: Failed to generate postcondition after 3 attempts"


def generate_postconditions_for_task(model, task: dict) -> dict:
    """Generate postconditions using all three strategies for a single task ID."""
    task_id = task["task_id"]
    prompt = task["prompt"]
    function_code = task["code"]
    
    print(f"Generating postconditions for task ID {task_id}...")
    
    # Generate using three strategies
    strategies = {
        "naive": create_naive_prompt,
        "few_shot": create_few_shot_prompt,
        "chain_of_thought": create_cot_prompt
    }
    
    generated = {}
    for strategy_name, prompt_fn in strategies.items():
        print(f"  Strategy: {strategy_name}")
        strategy_prompt = prompt_fn(prompt, function_code)
        response = call_llm_with_retry(model, strategy_prompt)
        postcondition = extract_postcondition(response)
        generated[strategy_name] = postcondition
    
    return {
        "task_id": task_id,
        "function_code": function_code,
        "generated_postconditions": generated
    }


def load_processed_dataset():
    """Load the processed MBPP dataset."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_generated_postconditions(data: list):
    """Save generated postconditions to JSON file."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {OUTPUT_FILE}")


def load_existing_postconditions():
    """Load existing postconditions if file exists."""
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None


def needs_regeneration(postcondition_entry: dict) -> bool:
    """Check if a postcondition entry needs regeneration."""
    if not postcondition_entry:
        return True
    
    postconditions = postcondition_entry.get("generated_postconditions", {})
    
    # Check if any strategy failed or is missing
    for strategy in ["naive", "few_shot", "chain_of_thought"]:
        pc = postconditions.get(strategy, "")
        if not pc or "Failed to extract postcondition" in pc:
            return True
    
    return False


def get_user_choice():
    """Display menu and get user choice for handling existing postconditions."""
    print("\n" + "=" * 70)
    print("EXISTING POSTCONDITIONS DETECTED")
    print("=" * 70)
    print("\nThe file 'generated_postconditions.json' already exists.")
    print("\nPlease select an option:")
    print("\n  [1] Regenerate only failed/missing postconditions (RECOMMENDED)")
    print("      - Skips functions with valid postconditions")
    print("      - Only generates for failed extractions or missing entries")
    print("      - Preserves existing valid postconditions")
    print("\n  [2] Regenerate all postconditions from scratch")
    print("      - Deletes existing file")
    print("      - Generates fresh postconditions for all functions")
    print("      - May incur additional API costs")
    print("\n" + "=" * 70)
    
    while True:
        choice = input("\nEnter your choice [1/2] (default: 1): ").strip()
        
        if choice == "" or choice == "1":
            return 1
        elif choice == "2":
            return 2
        else:
            print("Invalid choice. Please enter 1 or 2.")


def update_postcondition_file(new_entry: dict, all_entries: list):
    """Update the postcondition file with a new entry immediately."""
    # Find and update or append the entry
    updated = False
    for i, entry in enumerate(all_entries):
        if entry["task_id"] == new_entry["task_id"]:
            all_entries[i] = new_entry
            updated = True
            break
    
    if not updated:
        all_entries.append(new_entry)
    
    # Save immediately
    save_generated_postconditions(all_entries)


def main():
    """Main execution function."""
    print("=" * 70)
    print(f"POSTCONDITION GENERATION USING MODEL: {MODEL_NAME}")
    print("=" * 70)
    
    # Configure Gemini
    model = configure_gemini()
    
    # Load dataset
    dataset = load_processed_dataset()
    print(f"\nLoaded {len(dataset)} functions from dataset")
    
    # Check for existing postconditions
    existing_postconditions = load_existing_postconditions()
    regenerate_all = False
    functions_to_process = []
    
    if existing_postconditions:
        choice = get_user_choice()
        
        if choice == 2:
            # Regenerate all
            regenerate_all = True
            functions_to_process = dataset
            existing_postconditions = []
            print(f"\n→ Mode: Regenerating ALL {len(functions_to_process)} postconditions")
        else:
            # Regenerate only failed/missing
            existing_dict = {entry["task_id"]: entry for entry in existing_postconditions}
            
            for task in dataset:
                task_id = task["task_id"]
                existing_entry = existing_dict.get(task_id)
                
                if not existing_entry or needs_regeneration(existing_entry):
                    functions_to_process.append(task)
            
            print(f"\n→ Mode: Regenerating only failed/missing postconditions")
            print(f"→ functions with valid postconditions: {len(dataset) - len(functions_to_process)}")
            print(f"→ functions requiring generation: {len(functions_to_process)}")
            
            if len(functions_to_process) == 0:
                print("\n✓ All postconditions are already valid!")
                print("  No generation needed.")
                return
    else:
        # No existing file
        regenerate_all = True
        functions_to_process = dataset
        existing_postconditions = []
        print(f"\n→ No existing postconditions found")
        print(f"→ Generating postconditions for all {len(functions_to_process)} functions")
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate postconditions for selected functions
    print("\n" + "=" * 70)
    print("GENERATION IN PROGRESS")
    print("=" * 70 + "\n")
    
    all_entries = existing_postconditions if not regenerate_all else []
    
    for i, task in enumerate(functions_to_process, 1):
        print(f"[{i}/{len(functions_to_process)}] Task {task['task_id']}")
        result = generate_postconditions_for_task(model, task)
        
        # Immediately update the file
        update_postcondition_file(result, all_entries)
        print(f"  ✓ Saved to file\n")
    
    print("=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nTotal entries in file: {len(all_entries)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
