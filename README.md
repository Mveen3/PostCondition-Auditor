# Postcondition Auditor: Automated Evaluation of LLM-Generated Postconditions

A comprehensive automated system for generating and evaluating postconditions for Python functions using Large Language Models (LLMs). This project implements a complete pipeline from dataset processing to multi-dimensional evaluation (correctness, completeness, soundness) with detailed visualization and analysis.

## 📋 Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Pipeline Components](#pipeline-components)
- [Technologies & Libraries](#technologies--libraries)
- [Setup & Installation](#setup--installation)
- [Running the Pipeline](#-running-the-pipeline)
- [Output & Results](#output--results)

---

## 🎯 Overview

This project evaluates the quality of LLM-generated postconditions for Python functions across three critical dimensions:

1. **Correctness**: Do postconditions accurately capture the function's intended behavior?
2. **Completeness**: Do postconditions detect all possible bugs (measured via mutation testing)?
3. **Soundness**: Are postconditions free from hallucinated variables/attributes?

The system uses three different prompting strategies (Naive, Few-Shot, Chain-of-Thought) to generate postconditions and compares their effectiveness.

---

## 📁 Project Structure

```
Postcondition_Auditor/
├── Dockerfile                          # Container configuration
├── requirements.txt                    # Python dependencies
├── .env                               # API keys
└── src/
    ├── 01_process_dataset.py         # MBPP dataset sampling & preprocessing
    ├── 02_generate_postconditions.py # LLM-based postcondition generation
    ├── 03_correctness_evaluation.py  # Test case generation & correctness testing
    ├── 04_completeness_evaluation.py # Mutation analysis for completeness
    ├── 05_soundness_evaluation.py    # Hallucination detection
    ├── 06_summary_n_visualization.py # Metrics computation & visualization
    ├── dataset/
    │   ├── raw_mbpp.json             # Original MBPP dataset
    │   ├── processed_mbpp.json       # 50 randomly selected functions from MBPP dataset
    │   ├── generated_postconditions.json  # LLM-generated postconditions
    │   └── test_cases.json           # Hypothesis-generated test cases
    └── reports/
        ├── correctness_report.json   # Correctness evaluation results
        ├── completeness_report.json  # Mutmut-style mutation testing results
        ├── soundness_report.json     # Soundness evaluation results
        ├── analysis_summary.txt      # Comprehensive text report
        └── dashboard.png             # Comprehensive visualization dashboard
```

---

## 🔧 Pipeline Components

### 1. Dataset Processing (`01_process_dataset.py`)

**Purpose**: Prepares a representative sample of Python functions from the MBPP dataset.

**Key Operations**:
- Loads the full MBPP (Mostly Basic Python Problems) dataset
- Randomly samples 50 functions ensuring diversity
- Validates function syntax and structure
- Extracts metadata (function name, parameters, test cases)
- Saves processed dataset to `processed_mbpp.json`

**Libraries Used**:
- `json`: Data serialization
- `random`: Random sampling
- `ast`: Python abstract syntax tree parsing for validation

**Output**: `src/dataset/processed_mbpp.json`

---

### 2. Postcondition Generation (`02_generate_postconditions.py`)

**Purpose**: Generates postconditions using Google's Gemini LLM with three different prompting strategies.

**Prompting Strategies**:
1. **Naive**: Direct request without examples
2. **Few-Shot**: Includes 3 example function-postcondition pairs
3. **Chain-of-Thought**: Step-by-step reasoning guidance

**Key Operations**:
- Connects to Google Gemini API (via `google-generativeai`)
- Generates postconditions for each function using all three strategies
- Implements retry logic with exponential backoff for API resilience
- Validates generated postconditions for Python syntax
- Stores results with strategy metadata

**Libraries Used**:
- `google-generativeai`: Google Gemini LLM API client
- `python-dotenv`: Environment variable management for API keys
- `ast`: Syntax validation of generated postconditions
- `time`, `random`: Retry logic and rate limiting

**Configuration**:
- Model: `gemini-2.5-flash` (configurable)
- Temperature: 0.1 (low for deterministic outputs)
- Max retries: 3 per function

**Output**: `src/dataset/generated_postconditions.json`

---

### 3. Correctness Evaluation (`03_correctness_evaluation.py`)

**Purpose**: Tests if postconditions correctly describe function behavior using property-based testing.

**Test Generation Mechanism**:
- Uses **Hypothesis** library for intelligent test case generation
- Infers appropriate strategies from MBPP example test cases
- Generates 1000 diverse test cases per function
- Implements smart type inference (lists, tuples, strings, integers, dictionaries, etc.)
- Includes infinite loop protection with timeouts

**Key Features**:
- **Strategy Inference**: Analyzes example test cases to determine input types and ranges
- **Seed-Based Generation**: Starts with MBPP examples, then generates variations
- **Stall Detection**: Stops if no progress for 50 consecutive batches
- **JSON Serialization**: Ensures all test cases are serializable
- **User Interaction**: Prompts to reuse existing test cases (default: yes)

**Evaluation Process**:
1. Execute function with generated test inputs
2. Capture actual output
3. Check if postcondition holds for input-output pair
4. Report pass/fail for each strategy

**Libraries Used**:
- `hypothesis`: Property-based test generation framework
- `signal`: Timeout protection for infinite loops
- `ast`: Function parsing and parameter extraction
- `json`: Test case serialization

**Output**: 
- `src/dataset/test_cases.json` (1000 test cases per function)
- `src/reports/correctness_report.json`

---

### 4. Completeness Evaluation (`04_completeness_evaluation.py`)

**Purpose**: Measures how well postconditions detect bugs using Mutmut-style mutation testing.

**Mutation Testing Approach** (Mutmut-Inspired):
- Generates exactly 5 unique mutants per function using standardized mutation operators
- Filters duplicate and equivalent mutants for quality assurance
- Implements timeout protection to prevent hanging (30s per function)

**Standardized Mutation Operators**:
1. **ROR (Relational Operator Replacement)**:
   - Standard: `>` ↔ `<`, `>=` ↔ `<=`, `==` ↔ `!=`
   - Aggressive: `>` → `==`, `>=` → `<`, etc.

2. **AOR (Arithmetic Operator Replacement)**:
   - `+` ↔ `-`, `*` ↔ `/`, `%` → `*`

3. **LOR (Logical Operator Replacement)**:
   - `and` ↔ `or`

4. **CRP (Constant Replacement)**:
   - Standard: `0` → `1`, `n` → `n+1`
   - Aggressive: `n` → `n*2`

5. **UOI (Unary Operator Insertion/Deletion)**:
   - Remove `not`, change `-x` → `+x`

6. **RSM (Return Statement Mutation)**:
   - Replace return value with `None`

**Multi-Strategy Mutant Generation**:
1. **Standard mutations**: Default operator replacements
2. **Aggressive mutations**: Alternative mutation patterns for diversity
3. **Compound mutations**: Apply 2 mutations simultaneously (limited to 20 attempts)
4. **Constant variations**: Off-by-one errors in numeric constants
5. **Smart padding**: Further mutate existing mutants if needed
6. **Last resort duplicates**: Ensures exactly 5 mutants per function

**Equivalence Detection**:
- Tests mutants against sample test cases (max 10)
- Filters semantically equivalent mutants (same behavior as original)
- 2-second timeout per equivalence check

**Evaluation Process**:
1. Generate 5 unique, non-equivalent mutants per function
2. Run postcondition against each mutant with test cases (max 100)
3. If postcondition fails → mutant is "killed" (good!)
4. Calculate kill rate percentage: `(killed / total) * 100`

**Performance Optimizations**:
- Timeout protection at multiple levels (equivalence check, test execution, overall generation)
- Limited loop iterations to prevent infinite loops
- Reduced test case sampling for efficiency

**Libraries Used**:
- `ast`: Abstract syntax tree manipulation for mutations
- `copy`: Deep copying AST for safe mutations
- `signal`: Multi-level timeout protection
- `json`: Result serialization

**Metrics**: Kill rate percentage (0-100%) per strategy

**Output**: `src/reports/completeness_report.json`

---

### 5. Soundness Evaluation (`05_soundness_evaluation.py`)

**Purpose**: Detects hallucinated variables, functions, or attributes in postconditions.

**Hallucination Detection**:
Checks if postcondition references any identifier that doesn't exist in:
- Function parameters
- Built-in Python functions (`len`, `sum`, `max`, etc.)
- Standard library modules
- The `result` variable (function output)

**Validation Process**:
1. Parse postcondition code into AST
2. Extract all variable names, function calls, and attribute accesses
3. Compare against allowed identifiers
4. Flag any unknown references as hallucinations

**Common Hallucinations Detected**:
- Non-existent parameters
- Made-up helper functions
- Incorrect attribute names
- Undefined variables

**Libraries Used**:
- `ast`: AST parsing and identifier extraction
- `builtins`: Built-in function validation

**Output**: `src/reports/soundness_report.json`

---

### 6. Summary & Visualization (`06_summary_n_visualization.py`)

**Purpose**: Aggregates results, computes metrics, and generates a comprehensive dashboard.

**Metrics Computed**:

**Correctness Metrics**:
- Pass rate per strategy
- Per-function correctness distribution

**Completeness Metrics**:
- Mean kill rate per strategy
- Median kill rate
- Standard deviation
- Min/Max kill rates
- High/Low performer counts

**Soundness Metrics**:
- Sound postcondition percentage
- Hallucination rate

**Combined Metrics**:
- Perfect postconditions (Valid + Strong + Sound)
- Valid + Sound combinations
- Valid + Strong combinations
- Sound + Strong combinations

**Cross-Metric Analysis**:
- Strategy comparison across all dimensions
- Overall weighted scores (40% Correctness, 40% Completeness, 20% Soundness)
- Improvements over naive baseline
- Consistency analysis (Coefficient of Variation)
- Success stories & challenging functions identification

**Comprehensive Dashboard** (`dashboard.png`):
1. **Core Metrics Comparison**: Grouped bar chart showing Correctness, Completeness, Soundness per strategy
2. **Completeness Strength**: Stacked bar chart of High vs Low performers
3. **Consistency Analysis**: Coefficient of Variation comparison
4. **Combined Metrics Heatmap**: Color-coded matrix showing % of functions meeting multiple criteria
5. **Overall Weighted Score**: Strategy ranking by composite score
6. **Improvement vs Baseline**: Horizontal bar chart showing Few-Shot and CoT deltas
7. **Summary Table**: Success stories and challenges count

**Libraries Used**:
- `matplotlib`: Core plotting library with GridSpec for dashboard layout
- `numpy`: Numerical computations
- `statistics`: Statistical measures (mean, median, stdev)

**Output**: 
- `src/reports/analysis_summary.txt` (comprehensive text report)
- `src/reports/dashboard.png` (comprehensive dashboard)

---

## 🛠 Technologies & Libraries

### Core Dependencies

| Library | Purpose |
|---------|---------||
| `google-generativeai` | Google Gemini LLM API client |
| `python-dotenv` | Environment variable management |
| `hypothesis` | Property-based test generation |
| Custom Mutmut-style | Standardized mutation operators (ROR, AOR, LOR, CRP, UOI, RSM) |
| `matplotlib` | Data visualization & dashboard generation |
| `numpy` | Numerical computations |

### Python Standard Library

- `ast`: Abstract syntax tree manipulation
- `json`: JSON serialization/deserialization
- `pathlib`: Modern file path handling
- `signal`: Timeout and signal handling
- `copy`: Deep copying for safe mutations
- `random`: Random sampling and seeding
- `statistics`: Statistical computations
- `typing`: Type hints

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.12+ (recommended)
- Google Gemini API key
- Docker (for containerized deployment)

### Local Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Mveen3/PostCondition-Auditor
   cd Postcondition_Auditor
   ```

2. **Configure API key**:
   Create a `.env` file in the project root:
   ```bash
   # Paste your Gemini API key in the following format
   GEMINI_API_KEY= AIzaSyA0cYaeXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```

3. **Prepare dataset**:
   Place `raw_mbpp.json` in `src/dataset/` directory (or the system will download it automatically if connected).

4. **Building the Docker Image**

    ```bash
    docker build -t postcondition-auditor .
    ```

---

## ⚙️ Running the Pipeline

```bash
# Initializing Docker
docker run -it -v "$(pwd)":/app postcondition-auditor

# Random 50 MBPP function generation from raw_mbpp.json
python3 src/01_process_dataset.py

# Postcondition generation (requires API key)
python3 src/02_generate_postconditions.py

# Correctness evaluation
python3 src/03_correctness_evaluation.py

# Completeness evaluation
python3 src/04_completeness_evaluation.py

# Soundness evaluation
python3 src/05_soundness_evaluation.py

# Summary & visualization
python3 src/06_summary_n_visualization.py
```

---

## 📊 Output & Results

### Generated Files

After running the complete pipeline, you'll have:

#### Dataset Files
- `src/dataset/processed_mbpp.json`: 50 sampled functions with metadata
- `src/dataset/generated_postconditions.json`: LLM-generated postconditions (3 per function)
- `src/dataset/test_cases.json`: 1000 test cases per function (50,000 total)

#### Evaluation Reports
- `src/reports/correctness_report.json`: Binary pass/fail per function per strategy
- `src/reports/completeness_report.json`: Kill rate percentages (0-100)
- `src/reports/soundness_report.json`: Sound/hallucinated flags per function

#### Analysis Outputs
- `src/reports/analysis_summary.txt`: Comprehensive text report with:
  - Overall metrics per strategy
  - Statistical analysis (mean, median, std dev)
  - Strategy rankings and comparisons
  - Success stories and challenging functions
  - Consistency analysis

#### Dashboard
- `src/reports/dashboard.png`: Single comprehensive visualization containing:
  - Core metrics comparison (Correctness, Completeness, Soundness)
  - High vs Low performer analysis
  - Consistency analysis (Coefficient of Variation)
  - Combined metrics heatmap
  - Overall weighted scores
  - Improvement over baseline chart
  - Success stories & challenges summary table

### Expected Results Structure

**Correctness Report**:
```json
{
  "625": {
    "naive": true,
    "few_shot": true,
    "chain_of_thought": false
  },
  ...
}
```

**Completeness Report**:
```json
{
  "625": {
    "naive": 80,
    "few_shot": 100,
    "chain_of_thought": 60
  },
  ...
}
```

**Soundness Report**:
```json
{
  "625": {
    "naive": true,
    "few_shot": false,
    "chain_of_thought": true
  },
  ...
}
```

---


## 🔍 Key Features

### Intelligent Test Generation
- **Hypothesis Integration**: Leverages property-based testing for diverse, edge-case-rich test suites
- **Type Inference**: Automatically infers correct input types from examples
- **Infinite Loop Protection**: 10-second timeout per test case + stall detection

### Robust Mutation Testing (Mutmut-Inspired)
- **6 Standardized Mutation Operators**: ROR, AOR, LOR, CRP, UOI, RSM (research-proven)
- **Equivalence Detection**: Filters mutants with identical behavior to original
- **Multi-Strategy Generation**: Standard → Aggressive → Compound → Variations → Padding
- **Timeout Protection**: 30-second limit per function, 2-second per equivalence check
- **Quality Assurance**: Guarantees exactly 5 unique, non-equivalent mutants per function
- **Efficient Evaluation**: Uses up to 100 test cases per mutant for performance

### Comprehensive Analysis
- **Multi-Dimensional Evaluation**: Correctness, completeness, and soundness
- **Statistical Rigor**: Mean, median, standard deviation, distribution analysis
- **Visual Insights**: Multiple chart types for different perspectives

### Production-Ready
- **Error Handling**: Graceful failure handling at every stage
- **Retry Logic**: API calls with exponential backoff
- **Logging**: Detailed progress indicators and warnings
- **Reproducibility**: Fixed random seeds where applicable

---

## 📝 Notes & Best Practices

### Test Case Generation
- **First Run**: Takes 15-30 minutes to generate 50,000 test cases
- **Subsequent Runs**: Prompts to reuse existing test cases (recommended)
- **Storage**: `test_cases.json` is ~50-100 MB (depends on function complexity)

### API Usage
- **Rate Limiting**: Built-in delays between API calls
- **Cost**: ~50 functions × 3 strategies = 150 API calls (minimal cost with Gemini)
- **Retries**: Automatic retry on transient failures

### Performance Optimization
- **Parallel Execution**: Modules are independent after Step 2
- **Caching**: Reuse test cases, postconditions, and evaluation reports
- **Resource Usage**: Peak memory during correctness evaluation (~2-4 GB)

---

## 🎓 Research Context

This project implements an automated evaluation framework for assessing the quality of LLM-generated postconditions. It addresses the challenge of ensuring formal specifications (postconditions) correctly, completely, and soundly describe function behavior.

**Key Research Questions**:
1. Which prompting strategy produces the most correct postconditions?
2. How complete are LLM-generated postconditions in detecting bugs?
3. To what extent do LLMs hallucinate non-existent program elements?

**Methodology**:
- Dataset: MBPP (Mostly Basic Python Problems)
- Sample Size: 50 functions
- Test Cases: 1000 per function (Hypothesis-generated)
- Mutants: 5 per function (Mutmut-inspired generation with equivalence filtering)
- LLM: Google Gemini 2.5 Flash


---

