## Project Status (As of Nov 2)

### Today's Progress

We made a major strategic pivot today. We identified that our original prompts were generating natural language (text), which is impossible to use for the "Correctness" and "Completeness" evaluation tasks.

To solve this, we re-engineered our entire "Prompting Engine" to follow a new "code-only" strategy.

* **Engineered New Prompts:** We re-wrote all three prompt functions (`generate_naive_prompt`, `generate_few_shot_prompt`, `generate_cot_prompt`) to *specifically* instruct the LLM to return a single-line, runnable Python assertion.
* **Created "Smart" Helper:** We built a new helper function, `get_function_params`, to make our new prompts "smarter" by dynamically finding and inserting the function's parameter names (e.g., `test_tup1, test_tup2`).
* **Built New Parsers:** We created new parser functions (`parse_code_response`, `parse_cot_response`) designed to find and clean the new code-based assertions from the LLM's response, including stripping markdown.

### Current Status: 🛑 BLOCKED

The full run of our new `prompt_engine.py` is failing. Our new `get_function_params` helper function is failing on *some* (but not all) of the functions from our dataset.

The log shows multiple warnings: `WARNING: Could not parse params for code. Error: expected an indented block after function definition...`

This error is happening because `inspect.cleandoc` (which we're using to clean the function code before parsing) is not the right tool for the job. It's incorrectly stripping the indentation from the function's body, which causes the `exec()` command to fail.

### Next Steps (How to Fix This)

When we start again, we need to fix this bug:

1.  **Import a new library:** Add `import textwrap` to the top of `src/prompt_engine.py`.
2.  **Update `get_function_params`:** In the `get_function_params` function, find this line:
    ```python
    function_code = inspect.cleandoc(function_code)
    ```
    And change it to this:
    ```python
    function_code = textwrap.dedent(function_code)
    ```
3.  **Re-run the script:** Run `python src/prompt_engine.py`. This should fix the parsing warnings and allow the script to run to completion, generating our final `generated_postconditions.json` file.
