import json
import ast  # Abstract Syntax Tree library
import os

INPUT_FILE = "generated_postconditions.json"
OUTPUT_FILE = "evaluation_plan.json"

def load_generated_postconditions():
    """Loads the results from our prompt_engine.py script."""
    try:
        with open(INPUT_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found. Run prompt_engine.py first.")
        return None

def is_postcondition_testable(postcondition_str: str) -> bool:
    """
    Checks if a postcondition string is valid Python code by
    trying to parse it with the 'ast' library.
    """
    if not postcondition_str:
        return False
    try:
        # ast.parse() will raise a SyntaxError if the string
        # is not valid Python code.
        ast.parse(postcondition_str)
        return True
    except SyntaxError:
        return False

def main():
    """
    Main function to triage all 150 postconditions.
    It will tag each one as "testable" (code) or "untestable" (text).
    """
    print(f"Starting triage of {INPUT_FILE}...")
    
    all_results = load_generated_postconditions()
    
    if not all_results:
        print("No data to process. Exiting.")
        return

    evaluation_plan = []
    testable_count = 0

    # Loop through each of the 50 functions
    for result in all_results:
        task_id = result.get('task_id')
        postconditions = result.get('generated_postconditions', {})
        
        # A new dictionary to store our triage results
        plan_item = {
            "task_id": task_id,
            "function_code": result.get('function_code'),
            "postconditions": {}
        }
        
        # Check all 3 postconditions (naive, few_shot, cot)
        for strategy, post_str in postconditions.items():
            is_testable = is_postcondition_testable(post_str)
            
            plan_item["postconditions"][strategy] = {
                "postcondition_string": post_str,
                "is_testable": is_testable
            }
            
            if is_testable:
                testable_count += 1
                
        evaluation_plan.append(plan_item)

    # Save the new plan to our output file
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(evaluation_plan, f, indent=2)
        print(f"\n--- Triage Complete ---")
        print(f"Found {testable_count} testable code-based postconditions (out of 150).")
        print(f"Evaluation plan saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f"\n--- ERROR: Failed to save results ---")
        print(e)

if __name__ == "__main__":
    main()