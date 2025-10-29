# Postcondition Auditor

The **Postcondition Auditor** is a Python-based project designed to evaluate the ability of Large Language Models (LLMs) to automatically generate and validate postconditions for given functions. Postconditions are logical assertions that describe the expected state after a function executes.  

## Problem Overview
Traditional verification of postconditions is manual, time-consuming, and error-prone. This project explores how LLMs can assist in generating postconditions more efficiently and provides a framework to test their quality and reliability.

## Approach
- **LLM Prompting Strategies**  
  - *Naive Prompt* → Direct zero-shot instruction  
  - *Few-Shot Prompt* → Uses handpicked examples as references  
  - *Chain-of-Thought Prompt* → Encourages reasoning about function goals and edge cases  

- **Dataset**  
  - A curated subset of 50 functions from the MBPP dataset (with implementations and I/O test cases).  

- **Evaluation Metrics**  
  - **Correctness** → Validity of generated postconditions  
  - **Completeness** → Coverage and strength of assertions  
  - **Soundness** → Reliability of generated conditions  

- **Tech Stack**  
  - Python 3.10+  
  - DeepSeek-Coder (LLM baseline)  
  - Pytest + Hypothesis (testing framework)  
  - Mutmut (mutation testing)  
  - Python AST (static analysis for validation)  
  - Pandas, Seaborn, Matplotlib (data analysis & visualization)  
  - Git (version control)  

## Current Status
The project is under active development.  
Planned deliverables include:  
- Automated framework for LLM-based postcondition evaluation  
- Benchmarks comparing different prompting strategies  
- Visualization of performance metrics  

## How to Run
Instructions and usage examples will be added as development progresses.
---
