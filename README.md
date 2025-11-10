# 🧠 Postcondition Auditor Project

This project is an evaluation framework to analyze the effectiveness of LLM prompting strategies for generating software postconditions.
It is part of the **Software Systems Development Course at IIIT Hyderabad**.

---

## 🎯 Project Goal
To design a **novel evaluation framework** and conduct a **comparative analysis** of three distinct LLM prompting strategies:

1.  **Naive Prompting**
2.  **Few-Shot Prompting**
3.  **Chain-of-Thought Prompting**

These strategies will be measured against three metrics: **Correctness (Validity)**, **Completeness (Strength)**, and **Soundness (Reliability)**.

---

## 🚀 Current Status

### ✅ Phase 1: Experimental Setup (Completed)
We have successfully completed the entire data generation phase.

* **Data Pipeline (`src/build_dataset.py`):**
    * Reads the `sanitized-mbpp.json` dataset.
    * Filters 50 specific functions listed in `task_ids.txt`.
    * Outputs a clean `input_50_functions.json` file.

* **LLM Client (`src/llm_client.py`):**
    * Connects to the **Groq API** (using Llama) to fetch all LLM responses.

* **"Code-Only" Prompting Engine (`src/prompt_engine.py`):**
    * Pivoted from our initial "natural language" strategy to a new "code-only" strategy.
    * Re-engineered all **3 prompt functions** (Naive, Few-Shot, CoT) to instruct the LLM to return a single, runnable Python assertion.
    * Includes a helper (`get_function_params`) to make prompts "smarter" by dynamically injecting function parameter names.

* **Final Dataset (`generated_postconditions.json`):**
    * Successfully ran the new engine on all 50 functions.
    * Generated our final dataset: a JSON file containing **150 testable code assertions** (50 functions x 3 strategies).

### 🧩 Phase 2: Evaluation Framework (In Progress)

* **Task 1: Correctness (Validity) (`src/evaluate_correctness.py`):**
    * This is our current focus.
    * The script loads our 150 assertions and uses the `hypothesis` library to run property-based tests on each one.

---

## 🛑 CURRENT BLOCKER: Fixing the Evaluation Script

The `evaluate_correctness.py` script is **failing**. We have successfully debugged initial `kwargs` errors and are now facing two new, more complex problems identified in the run logs:

1.  **The "Strategy Fail" (Wrong Data Type):** Our `hypothesis` strategy generator (`get_strategy_for_param`) is too simple. It's feeding the wrong *kind* of random data to the functions (e.g., sending an `int` to a function that expects a `list` or `string`).
    * `Task 11: FAIL (replace() argument 1 must be str, not int)`
    * `Task 12: FAIL ('int' object is not iterable)`

2.  **The "Scope Fail" (Missing Imports/Helpers):** Our script's `eval()` command is crashing because it doesn't have access to the libraries (`math`, `heapq`) or helper functions (`binary_search`) that the original code and the assertions need.
    * `Task 4: FAIL (name 'hq' is not defined)`
    * `Task 223: FAIL (name 'binary_search' is not defined)`

**Our immediate next step is to fix these two bugs in `src/evaluate_correctness.py`.**

---

## 🛠️ How to Run This Project

### 1. Prerequisites
Make sure you have the following installed:

* **Git**
* **Docker Desktop** (or the Docker Engine)

### 2. Setup Instructions

```bash
# 1. Clone the repository
git clone <your-repository-url>
cd postcondition-auditor

# 2. Create the environment file for your API key
#    IMPORTANT: This file is ignored by Git.
#    Replace "YOUR_GROQ_API_KEY_GOES_HERE" with your actual Groq API key.
echo 'GROQ_API_KEY="YOUR_GROQ_API_KEY_GOES_HERE"' > .env

# 3. Build the Docker image
#    This installs Python, requests, python-dotenv, and hypothesis.
docker build -t auditor-env .

# 4. Run the Docker container
#    This starts an interactive terminal INSIDE the container.
docker run -it --rm -v .:/app auditor-env

```bash
# --- STEP 1: Run the Data Pipeline (Only needs to be run once) ---
# (Input: task_ids.txt, sanitized-mbpp.json)
# (Output: input_50_functions.json)
python src/build_dataset.py

# --- STEP 2: Run the Prompting Engine (Only needs to be run once) ---
# (Input: input_50_functions.json)
# (Output: generated_postconditions.json)
python src/prompt_engine.py

# --- STEP 3: Run the Correctness Evaluation (This is our current task) ---
# (Input: generated_postconditions.json)
# (Output: correctness_results.json)
python src/evaluate_correctness.py