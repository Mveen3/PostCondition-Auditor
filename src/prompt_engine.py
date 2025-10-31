#Havent gone through the code yet

import json
import os

# Import the function you already built and tested!
try:
    from llm_client import get_llm_response
except ImportError:
    print("Error: llm_client.py not found or get_llm_response function is missing.")
    exit()

INPUT_FILE = "input_50_functions.json"


def load_functions(input_file):
    """Loads the 50 functions from our curated JSON file."""
    try:
        with open(input_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_file}")
        return None


def generate_naive_prompt(function_code: str) -> str:
    """
    Generates a direct, zero-shot prompt for postcondition generation.
    """
    prompt = f"""
Here is a Python function:

```python
{function_code}
```

Write a formal postcondition for this function.
The postcondition should be a single, precise logical assertion
that describes the state after the function executes.
Start your response only with the postcondition.
"""

    return prompt


def main():
    """
    Main function for the Prompting Strategy Engine.
    """
    print("Starting Prompt Engine...")

    functions = load_functions(INPUT_FILE)

    if not functions:
        print(f"No functions loaded from {INPUT_FILE}. Exiting.")
        return

    print(f"Successfully loaded {len(functions)} functions.")

    # --- Let's test with just the first function ---
    first_function = functions[0]
    func_code = first_function.get('code')
    task_id = first_function.get('task_id')

    print(f"\n--- Processing test on Task ID: {task_id} ---")

    # --- Generate prompt for this function ---
    naive_prompt_string = generate_naive_prompt(func_code)

    print(f"\n--- Generated Naive Prompt ---\n{naive_prompt_string}")

    # Send this prompt to the LLM
    print("Sending Naive Prompt to LLM...")
    response = get_llm_response(naive_prompt_string)

    print(f"\n--- LLM Response (Naive) ---\n{response}")


if __name__ == "__main__":
    main()
