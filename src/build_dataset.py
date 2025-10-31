#Have not gone through the code yet

import json

def get_chosen_task_ids():
    """Reads the task_ids.txt file and returns a set of integers."""
    task_ids = set()
    try:
        with open('task_ids.txt', 'r') as f:
            for line in f:
                task_ids.add(int(line.strip()))
        print(f"Successfully loaded {len(task_ids)} task IDs.")
    except FileNotFoundError:
        print("Error: task_ids.txt not found. Make sure it's in the root folder.")
        return None
    return task_ids

def build_dataset(chosen_ids):
    """
    Loads 'sanitized-mbpp.json', filters for chosen_ids,
    cleans each function object, and saves the result.
    """
    if not chosen_ids:
        print("No task IDs loaded. Cannot build dataset.")
        return

    filtered_functions = []
    try:
        with open('sanitized-mbpp.json', 'r') as f:
            all_functions = json.load(f)
        
        print(f"Loaded {len(all_functions)} functions from sanitized-mbpp.json.")
        
        # Filter the functions
        for func in all_functions:
            if func.get('task_id') in chosen_ids:
                
                # --- THIS IS THE NEW PART ---
                # Create a new, clean dictionary with only the keys we need.
                clean_function = {
                    "task_id": func.get('task_id'),
                    "prompt": func.get('prompt'),
                    "code": func.get('code'),
                    "test_imports": func.get('test_imports', []), # Use default if key missing
                    "test_list": func.get('test_list', [])      # Use default if key missing
                }
                filtered_functions.append(clean_function)
                # ----------------------------

        print(f"Successfully filtered and cleaned {len(filtered_functions)} functions.")
        
        # Write the new, filtered list to our output file
        with open('input_50_functions.json', 'w') as f:
            json.dump(filtered_functions, f, indent=2)
            
        print(f"Successfully created 'input_50_functions.json'.")

    except FileNotFoundError:
        print("Error: sanitized-mbpp.json not found. Make sure it's in the root folder.")
    except Exception as e:
        print(f"An error occurred: {e}")

# --- This is how we'll run our functions ---
if __name__ == "__main__":
    chosen_ids = get_chosen_task_ids()
    build_dataset(chosen_ids)