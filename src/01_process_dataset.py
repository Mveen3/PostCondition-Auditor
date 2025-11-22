import json
import random
import os

def create_processed_dataset():
    """
    Reads the raw MBPP dataset, selects a random sample of 50 functions,
    and saves them to a new JSON file.
    """
        
    # Base directory where data is stored, relative to the project root
    BASE_DIR = "src/dataset"
    
    # Input file
    INPUT_FILE = os.path.join(BASE_DIR, "raw_mbpp.json")
    
    # Desired output file
    OUTPUT_FILE = os.path.join(BASE_DIR, "processed_mbpp.json")
    
    SAMPLE_SIZE = 50
    
    # Use a fixed seed for reproducible random sampling
    RANDOM_SEED = 42
    
    print("--- Starting Data Processing ---")
    
    try:
        # Step 1: Set the random seed
        random.seed(RANDOM_SEED)
        
        # Step 2: Read the raw dataset
        print(f"Loading data from {INPUT_FILE}...")
        with open(INPUT_FILE, 'r') as f:
            all_functions = json.load(f)
        
        total_functions = len(all_functions)
        print(f"Successfully loaded {total_functions} total functions.")

        # Step 3: Check if we have enough data and sample it
        if total_functions < SAMPLE_SIZE:
            print(f"Error: Source file has {total_functions} functions, but {SAMPLE_SIZE} were requested.")
            print("Please check your raw_mbpp.json file.")
            return
            
        print(f"Randomly sampling {SAMPLE_SIZE} functions...")
        sampled_functions = random.sample(all_functions, SAMPLE_SIZE)
        
        print(f"Sampling complete. {len(sampled_functions)} functions selected.")

        # Step 4: Write the new processed dataset
        print(f"Writing processed dataset to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(sampled_functions, f, indent=4)
        os.chmod(OUTPUT_FILE, 0o644)

        print(f"\nSuccessfully created {OUTPUT_FILE}.")
        print("--- Data Processing Complete ---")

    except FileNotFoundError:
        print(f"Error: Input file not found at {INPUT_FILE}.")
        print("Please ensure 'raw_mbpp.json' is in the 'src/dataset' directory.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {INPUT_FILE}. The file might be corrupted.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    create_processed_dataset()