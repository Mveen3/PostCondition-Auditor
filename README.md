# 🧠 Postcondition Auditor Project

This project is an evaluation framework to analyze the effectiveness of LLM prompting strategies for generating software postconditions.  
It is part of the **Software Systems Development Course at IIIT Hyderabad**.

---

## 🎯 Project Goal
To design a **novel evaluation framework** and conduct a **comparative analysis** of three distinct LLM prompting strategies:

1. **Naive Prompting**
2. **Few-Shot Prompting**
3. **Chain-of-Thought Prompting**

---

## 🚀 Current Progress

### ✅ Implemented
- **Data Pipeline (`src/build_dataset.py`)**
  - Reads the `sanitized-mbpp.json` dataset.
  - Filters 50 specific functions listed in `task_ids.txt`.
  - Outputs a clean `input_50_functions.json` file for experiments.

- **LLM Client (`src/llm_client.py`)**
  - Connects to the **Groq API** (using **Llama 3.1**) to fetch LLM responses.

- **Prompting Engine (`src/prompt_engine.py`)**
  - Loads the filtered 50 functions and begins postcondition generation using different strategies.

- **Naive Prompt Strategy** implemented.

### 🧩 In Progress
- **Few-Shot Prompt Strategy** (coming next).

---

## 🛠️ How to Run This Project

### 1. Prerequisites
Make sure you have the following installed:

- **Git**
- **Docker Desktop** (or the Docker Engine)

---

### 2. Setup Instructions

```bash
# 1. Clone the repository to your local machine
git clone <your-repository-url>
cd postcondition-auditor

# 2. Create the environment file for your API key
#    IMPORTANT: This file is ignored by Git and will NOT be uploaded.
#    Replace "YOUR_GROQ_API_KEY_GOES_HERE" with your actual Groq API key.
echo 'GROQ_API_KEY="YOUR_GROQ_API_KEY_GOES_HERE"' > .env

# 3. Build the Docker image (only once)
docker build -t auditor-env .

# 4. Run the Docker container
#    This command starts an interactive terminal INSIDE the container
#    and mounts your project folder.
docker run -it --rm -v .:/app auditor-env
