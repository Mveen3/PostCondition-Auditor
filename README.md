# Postcondition Auditor: Automated Evaluation of LLM-Generated Postconditions

A comprehensive automated system for generating and evaluating postconditions for Python functions using Large Language Models (LLMs). This project implements a complete pipeline from dataset processing to multi-dimensional evaluation (correctness, completeness, soundness) with detailed visualization and analysis.

## 📋 Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Pipeline Components](#pipeline-components)
- [Technologies & Libraries](#technologies--libraries)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [Output & Results](#output--results)
- [Docker Deployment](#docker-deployment)

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
zmyproject/
├── Dockerfile                          # Container configuration
├── requirements.txt                    # Python dependencies
├── .env                               # API keys (not tracked in git)
├── src/
│   ├── 01_process_dataset.py         # MBPP dataset sampling & preprocessing
│   ├── 02_generate_postconditions.py # LLM-based postcondition generation
│   ├── 03_correctness_evaluation.py  # Test case generation & correctness testing
│   ├── 04_completeness_evaluation.py # Mutation analysis for completeness
│   ├── 05_soundness_evaluation.py    # Hallucination detection
│   ├── 06_summary_n_visualization.py # Metrics computation & visualization
│   ├── dataset/
│   │   ├── raw_mbpp.json             # Original MBPP dataset
│   │   ├── processed_mbpp.json       # 50 sampled functions
│   │   ├── generated_postconditions.json  # LLM-generated postconditions
│   │   └── test_cases.json           # Hypothesis-generated test cases
│   └── evaluation/
│       ├── correctness_report.json   # Correctness evaluation results
│       ├── completeness_report.json  # Mutation testing results
│       ├── soundness_report.json     # Soundness evaluation results
│       ├── analysis_summary.txt      # Comprehensive text report
│       └── visualizations/           # Generated charts & plots
└── Ref_Material/                      # Reference documents
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
- Model: `gemini-1.5-flash` (configurable)
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
- `src/evaluation/correctness_report.json`

---

### 4. Completeness Evaluation (`04_completeness_evaluation.py`)

**Purpose**: Measures how well postconditions detect bugs using mutation testing.

**Mutation Testing Approach**:
- Generates 5 mutants per function using AST transformations
- Mutation operators:
  - **Comparison mutations**: `>` ↔ `>=`, `==` ↔ `!=`
  - **Arithmetic mutations**: `+` ↔ `-`, `*` ↔ `//`
  - **Range mutations**: Off-by-one errors (`range(n)` → `range(n+1)`)
  - **Subscript mutations**: Index changes (`arr[i]` → `arr[i+1]`)
  - **Constant mutations**: Numeric value changes
  - **Return mutations**: Return value modifications
  - **Boolean mutations**: `and` ↔ `or`

**Fallback Strategies**:
If standard mutations insufficient, applies:
- Compound mutations (2+ operators combined)
- Stacked mutations (mutating previous mutants)
- Exhaustive mutation attempts

**Evaluation Process**:
1. Generate mutants of original function
2. Run postcondition against mutant with test cases
3. If postcondition fails → mutant is "killed" (good!)
4. Calculate kill rate percentage

**Libraries Used**:
- `ast`: Abstract syntax tree manipulation for mutations
- `copy`: Deep copying AST for safe mutations
- `signal`: Timeout protection (1 second per test case)

**Metrics**: Kill rate percentage (0-100%) per strategy

**Output**: `src/evaluation/completeness_report.json`

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

**Output**: `src/evaluation/soundness_report.json`

---

### 6. Summary & Visualization (`06_summary_n_visualization.py`)

**Purpose**: Aggregates results, computes metrics, and generates visualizations.

**Metrics Computed**:

**Correctness Metrics**:
- Pass rate per strategy
- Per-function correctness distribution

**Completeness Metrics**:
- Mean kill rate per strategy
- Median kill rate
- Standard deviation
- Min/Max kill rates
- Distribution analysis

**Soundness Metrics**:
- Sound postcondition percentage
- Hallucination rate
- Most common hallucination types

**Cross-Metric Analysis**:
- Strategy comparison across all dimensions
- Correlation between metrics
- Best/worst performing functions

**Visualizations Generated**:
1. **Correctness Bar Chart**: Pass rates by strategy
2. **Completeness Distribution**: Box plots showing kill rate spread
3. **Soundness Comparison**: Sound vs hallucinated postconditions
4. **Comprehensive Heatmap**: All metrics across all strategies
5. **Per-Function Analysis**: Detailed breakdowns for each function
6. **Strategy Comparison**: Side-by-side radar charts

**Libraries Used**:
- `matplotlib`: Core plotting library
- `seaborn`: Statistical visualization and styling
- `numpy`: Numerical computations
- `statistics`: Statistical measures (mean, median, stdev)

**Output**: 
- `src/evaluation/analysis_summary.txt` (comprehensive text report)
- `src/evaluation/visualizations/*.png` (multiple charts)

---

## 🛠 Technologies & Libraries

### Core Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| `google-generativeai` | Latest | Google Gemini LLM API client |
| `python-dotenv` | Latest | Environment variable management |
| `hypothesis` | 6.x | Property-based test generation |
| `matplotlib` | Latest | Data visualization |
| `seaborn` | Latest | Statistical plots |
| `pandas` | Latest | Data manipulation |
| `pytest` | Latest | Testing framework (optional) |
| `mutmut` | Latest | Mutation testing (reference only) |

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
- Docker (optional, for containerized deployment)

### Local Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd zmyproject
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # OR
   venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API key**:
   Create a `.env` file in the project root:
   ```bash
   GEMINI_API_KEY=your_google_gemini_api_key_here
   ```

5. **Prepare dataset**:
   Place `raw_mbpp.json` in `src/dataset/` directory (or the system will download it automatically if connected).

---

## 📖 Usage

### Complete Pipeline Execution

Run the entire pipeline in sequence:

```bash
# Step 1: Process dataset (sample 50 functions)
python src/01_process_dataset.py

# Step 2: Generate postconditions using LLM
python src/02_generate_postconditions.py

# Step 3: Evaluate correctness (generates 1000 test cases per function)
# This step may take 30-60 minutes depending on function complexity
python src/03_correctness_evaluation.py

# Step 4: Evaluate completeness (mutation testing)
python src/04_completeness_evaluation.py

# Step 5: Evaluate soundness (hallucination detection)
python src/05_soundness_evaluation.py

# Step 6: Generate summary and visualizations
python src/06_summary_n_visualization.py
```

### Individual Module Execution

Each module can be run independently:

#### Dataset Processing
```bash
python src/01_process_dataset.py
```
- **Input**: `src/dataset/raw_mbpp.json`
- **Output**: `src/dataset/processed_mbpp.json`
- **Duration**: ~5 seconds

#### Postcondition Generation
```bash
python src/02_generate_postconditions.py
```
- **Input**: `src/dataset/processed_mbpp.json`
- **Output**: `src/dataset/generated_postconditions.json`
- **Duration**: ~5-10 minutes (50 functions × 3 strategies)
- **Note**: Requires valid `GEMINI_API_KEY` in `.env`

#### Correctness Evaluation
```bash
python src/03_correctness_evaluation.py
```
- **Input**: 
  - `src/dataset/processed_mbpp.json`
  - `src/dataset/generated_postconditions.json`
- **Output**: 
  - `src/dataset/test_cases.json`
  - `src/evaluation/correctness_report.json`
- **Duration**: ~30-60 minutes (generates 1000 test cases per function)
- **Interactive**: Prompts to reuse existing test cases if found

**User Prompt**:
```
✓ Found complete test cases for all 50 functions (1000 each)

Do you want to:
  1) Use existing test cases [default]
  2) Regenerate all test cases

Enter choice (1 or 2) [1]: 
```
- Press Enter or type `1` to reuse existing test cases (recommended)
- Type `2` to regenerate from scratch

#### Completeness Evaluation
```bash
python src/04_completeness_evaluation.py
```
- **Input**: 
  - `src/dataset/processed_mbpp.json`
  - `src/dataset/generated_postconditions.json`
  - `src/dataset/test_cases.json`
- **Output**: `src/evaluation/completeness_report.json`
- **Duration**: ~10-20 minutes (5 mutants per function)

#### Soundness Evaluation
```bash
python src/05_soundness_evaluation.py
```
- **Input**: `src/dataset/generated_postconditions.json`
- **Output**: `src/evaluation/soundness_report.json`
- **Duration**: ~1-2 minutes

#### Summary & Visualization
```bash
python src/06_summary_n_visualization.py
```
- **Input**: All three evaluation reports
- **Output**: 
  - `src/evaluation/analysis_summary.txt`
  - `src/evaluation/visualizations/*.png`
- **Duration**: ~30 seconds

---

## 📊 Output & Results

### Generated Files

After running the complete pipeline, you'll have:

#### Dataset Files
- `src/dataset/processed_mbpp.json`: 50 sampled functions with metadata
- `src/dataset/generated_postconditions.json`: LLM-generated postconditions (3 per function)
- `src/dataset/test_cases.json`: 1000 test cases per function (50,000 total)

#### Evaluation Reports
- `src/evaluation/correctness_report.json`: Binary pass/fail per function per strategy
- `src/evaluation/completeness_report.json`: Kill rate percentages (0-100)
- `src/evaluation/soundness_report.json`: Sound/hallucinated flags per function

#### Analysis Outputs
- `src/evaluation/analysis_summary.txt`: Comprehensive text report with:
  - Overall metrics per strategy
  - Statistical analysis (mean, median, std dev)
  - Best/worst performing functions
  - Detailed insights and recommendations

#### Visualizations
- `correctness_comparison.png`: Bar chart of pass rates
- `completeness_boxplot.png`: Distribution of kill rates
- `soundness_comparison.png`: Sound vs hallucinated counts
- `strategy_heatmap.png`: Multi-metric comparison
- Additional charts for detailed analysis

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

## 🐳 Docker Deployment

### Building the Docker Image

```bash
docker build -t postcondition-auditor .
```

### Running in Docker

#### Complete Pipeline
```bash
docker run --rm \
  -v $(pwd)/src:/app/src \
  -e GEMINI_API_KEY=your_api_key_here \
  postcondition-auditor \
  bash -c "
    python src/01_process_dataset.py &&
    python src/02_generate_postconditions.py &&
    python src/03_correctness_evaluation.py &&
    python src/04_completeness_evaluation.py &&
    python src/05_soundness_evaluation.py &&
    python src/06_summary_n_visualization.py
  "
```

#### Individual Steps
```bash
# Dataset processing
docker run --rm -v $(pwd)/src:/app/src postcondition-auditor python src/01_process_dataset.py

# Postcondition generation (requires API key)
docker run --rm -v $(pwd)/src:/app/src -e GEMINI_API_KEY=your_key postcondition-auditor python src/02_generate_postconditions.py

# Correctness evaluation (interactive - requires -it flags)
docker run --rm -it -v $(pwd)/src:/app/src postcondition-auditor python src/03_correctness_evaluation.py

# Completeness evaluation
docker run --rm -v $(pwd)/src:/app/src postcondition-auditor python src/04_completeness_evaluation.py

# Soundness evaluation
docker run --rm -v $(pwd)/src:/app/src postcondition-auditor python src/05_soundness_evaluation.py

# Summary & visualization
docker run --rm -v $(pwd)/src:/app/src postcondition-auditor python src/06_summary_n_visualization.py
```

### Docker Notes

- **Volume Mounting**: `-v $(pwd)/src:/app/src` ensures generated files persist on host
- **Environment Variables**: `-e GEMINI_API_KEY=...` passes API key securely
- **Interactive Mode**: `-it` flags required for steps with user prompts (correctness evaluation)
- **Automatic Cleanup**: `--rm` flag removes container after execution

---

## 🔍 Key Features

### Intelligent Test Generation
- **Hypothesis Integration**: Leverages property-based testing for diverse, edge-case-rich test suites
- **Type Inference**: Automatically infers correct input types from examples
- **Infinite Loop Protection**: 10-second timeout per test case + stall detection

### Robust Mutation Testing
- **7 Mutation Operators**: Comprehensive coverage of common bug patterns
- **Fallback Strategies**: Ensures 5 mutants per function even for simple code
- **Efficient Evaluation**: Uses only 100 test cases per mutant for performance

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
- **First Run**: Takes 30-60 minutes to generate 50,000 test cases
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

### Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'hypothesis'`
- **Solution**: Run `pip install -r requirements.txt` in activated virtual environment

**Issue**: API key errors during postcondition generation
- **Solution**: Verify `.env` file exists with valid `GEMINI_API_KEY`

**Issue**: Timeout errors during test generation
- **Solution**: Normal for complex recursive functions; system will skip and continue

**Issue**: Mutation generation fails for some functions
- **Solution**: System applies 7 fallback strategies; minimal impact on overall results

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
- Mutants: 5 per function (AST-based)
- LLM: Google Gemini 1.5 Flash

---

## 📄 License

This project is for research and educational purposes. Please ensure compliance with Google Gemini API terms of service and MBPP dataset license.

---

## 🤝 Contributing

For questions, issues, or contributions, please refer to the project repository or contact the maintainer.

---

## 📞 Support

If you encounter any issues running the pipeline:
1. Verify all dependencies are installed (`pip list`)
2. Check `.env` file contains valid API key
3. Ensure `src/dataset/raw_mbpp.json` exists
4. Review console output for specific error messages
5. Check `src/evaluation/analysis_summary.txt` for diagnostic information

---

**Happy Evaluating! 🚀**
