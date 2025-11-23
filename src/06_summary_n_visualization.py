"""
Unified Summary + Visualization Script for Postcondition Evaluation

Behavior:
- Reads correctness, completeness, and soundness reports
- Computes all metrics
- Generates analysis_summary.txt with detailed insights
- Generates all visualizations in src/reports/visualizations/
- Prints a quick summary to the console
"""

import json
import os
from typing import Dict, Tuple
from collections import defaultdict
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np


# Input report files
CORRECTNESS_REPORT = "src/reports/correctness_report.json"
COMPLETENESS_REPORT = "src/reports/completeness_report.json"
SOUNDNESS_REPORT = "src/reports/soundness_report.json"

# Outputs
SUMMARY_FILE = "src/reports/analysis_summary.txt"
OUTPUT_DIR = "src/reports/visualizations"

# Visualization config
COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1']  # Red, Teal, Blue
STRATEGY_NAMES = {
    'naive': 'Naive',
    'few_shot': 'Few-Shot',
    'chain_of_thought': 'Chain-of-Thought'
}

# Ensure output directory exists
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def load_reports() -> Tuple[Dict, Dict, Dict]:
    """Load all three evaluation reports."""
    with open(CORRECTNESS_REPORT, 'r') as f:
        correctness = json.load(f)

    with open(COMPLETENESS_REPORT, 'r') as f:
        completeness = json.load(f)

    with open(SOUNDNESS_REPORT, 'r') as f:
        soundness = json.load(f)

    return correctness, completeness, soundness


# Metrics Computation Functions
def calculate_correctness_metrics(correctness_data: Dict) -> Dict:
    """
    Calculate correctness (validity) metrics.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    metrics = {}

    for strategy in strategies:
        valid_count = sum(1 for task_results in correctness_data.values()
                          if task_results.get(strategy, False))
        total_count = len(correctness_data)
        percentage = (valid_count / total_count * 100) if total_count > 0 else 0

        metrics[strategy] = {
            'valid_postconditions': valid_count,
            'total_postconditions': total_count,
            'validity_percentage': round(percentage, 2),
            'invalid_postconditions': total_count - valid_count
        }

    return metrics


def calculate_completeness_metrics(completeness_data: Dict) -> Dict:
    """
    Calculate completeness (strength) metrics.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    metrics = {}

    for strategy in strategies:
        scores = [task_results.get(strategy, 0) for task_results in completeness_data.values()]

        metrics[strategy] = {
            'average_mutation_kill_score': round(statistics.mean(scores), 2),
            'median_mutation_kill_score': round(statistics.median(scores), 2),
            'min_mutation_kill_score': min(scores),
            'max_mutation_kill_score': max(scores),
            'std_dev_mutation_kill_score': round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
            'total_functions_evaluated': len(scores)
        }

        # Score distribution
        score_ranges = {
            '0-20%': sum(1 for s in scores if 0 <= s < 20),
            '20-40%': sum(1 for s in scores if 20 <= s < 40),
            '40-60%': sum(1 for s in scores if 40 <= s < 60),
            '60-80%': sum(1 for s in scores if 60 <= s < 80),
            '80-100%': sum(1 for s in scores if 80 <= s <= 100)
        }
        metrics[strategy]['score_distribution'] = score_ranges

        # High performers (>= 80%)
        high_performers = sum(1 for s in scores if s >= 80)
        metrics[strategy]['high_performers_count'] = high_performers
        metrics[strategy]['high_performers_percentage'] = round(high_performers / len(scores) * 100, 2)

        # Low performers (<= 40%)
        low_performers = sum(1 for s in scores if s <= 40)
        metrics[strategy]['low_performers_count'] = low_performers
        metrics[strategy]['low_performers_percentage'] = round(low_performers / len(scores) * 100, 2)

    return metrics


def calculate_soundness_metrics(soundness_data: Dict) -> Dict:
    """
    Calculate soundness (reliability) metrics.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    metrics = {}

    for strategy in strategies:
        sound_count = sum(1 for task_results in soundness_data.values()
                          if task_results.get(strategy, False))
        total_count = len(soundness_data)
        hallucinated_count = total_count - sound_count

        sound_percentage = (sound_count / total_count * 100) if total_count > 0 else 0
        hallucination_rate = (hallucinated_count / total_count * 100) if total_count > 0 else 0

        metrics[strategy] = {
            'sound_postconditions': sound_count,
            'hallucinated_postconditions': hallucinated_count,
            'total_postconditions': total_count,
            'sound_percentage': round(sound_percentage, 2),
            'hallucination_rate': round(hallucination_rate, 2)
        }

    return metrics


def calculate_combined_metrics(correctness_data: Dict, completeness_data: Dict,
                               soundness_data: Dict) -> Dict:
    """
    Calculate combined metrics across all three evaluation dimensions.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    combined = {}

    for strategy in strategies:
        all_three_pass = []
        valid_and_sound = []
        valid_and_strong = []
        sound_and_strong = []

        for task_id in correctness_data.keys():
            is_valid = correctness_data[task_id].get(strategy, False)
            is_sound = soundness_data[task_id].get(strategy, False)
            mutation_score = completeness_data[task_id].get(strategy, 0)
            is_strong = mutation_score >= 80

            if is_valid and is_sound and is_strong:
                all_three_pass.append(task_id)

            if is_valid and is_sound:
                valid_and_sound.append(task_id)

            if is_valid and is_strong:
                valid_and_strong.append(task_id)

            if is_sound and is_strong:
                sound_and_strong.append(task_id)

        total = len(correctness_data)

        combined[strategy] = {
            'perfect_postconditions_count': len(all_three_pass),
            'perfect_postconditions_percentage': round(len(all_three_pass) / total * 100, 2),
            'perfect_postcondition_task_ids': all_three_pass,

            'valid_and_sound_count': len(valid_and_sound),
            'valid_and_sound_percentage': round(len(valid_and_sound) / total * 100, 2),

            'valid_and_strong_count': len(valid_and_strong),
            'valid_and_strong_percentage': round(len(valid_and_strong) / total * 100, 2),

            'sound_and_strong_count': len(sound_and_strong),
            'sound_and_strong_percentage': round(len(sound_and_strong) / total * 100, 2)
        }

    return combined


def calculate_strategy_comparison(correctness_metrics: Dict, completeness_metrics: Dict,
                                  soundness_metrics: Dict) -> Dict:
    """
    Compare strategies head-to-head across all three dimensions.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']

    comparison = {
        'correctness_ranking': sorted(
            strategies,
            key=lambda s: correctness_metrics[s]['validity_percentage'],
            reverse=True
        ),
        'completeness_ranking': sorted(
            strategies,
            key=lambda s: completeness_metrics[s]['average_mutation_kill_score'],
            reverse=True
        ),
        'soundness_ranking': sorted(
            strategies,
            key=lambda s: soundness_metrics[s]['sound_percentage'],
            reverse=True
        )
    }

    # Overall weighted score
    overall_scores = {}
    for strategy in strategies:
        correctness_score = correctness_metrics[strategy]['validity_percentage']
        completeness_score = completeness_metrics[strategy]['average_mutation_kill_score']
        soundness_score = soundness_metrics[strategy]['sound_percentage']

        overall_score = (0.4 * correctness_score +
                         0.4 * completeness_score +
                         0.2 * soundness_score)

        overall_scores[strategy] = round(overall_score, 2)

    comparison['overall_scores'] = overall_scores
    comparison['overall_ranking'] = sorted(strategies, key=lambda s: overall_scores[s], reverse=True)
    comparison['best_overall_strategy'] = comparison['overall_ranking'][0]

    # Improvements over naive baseline
    baseline = 'naive'
    comparison['improvements_over_baseline'] = {}

    for strategy in ['few_shot', 'chain_of_thought']:
        improvements = {
            'correctness_improvement': round(
                correctness_metrics[strategy]['validity_percentage'] -
                correctness_metrics[baseline]['validity_percentage'], 2
            ),
            'completeness_improvement': round(
                completeness_metrics[strategy]['average_mutation_kill_score'] -
                completeness_metrics[baseline]['average_mutation_kill_score'], 2
            ),
            'soundness_improvement': round(
                soundness_metrics[strategy]['sound_percentage'] -
                soundness_metrics[baseline]['sound_percentage'], 2
            ),
            'overall_improvement': round(
                overall_scores[strategy] - overall_scores[baseline], 2
            )
        }
        comparison['improvements_over_baseline'][strategy] = improvements

    return comparison


def identify_challenging_functions(correctness_data: Dict, completeness_data: Dict,
                                   soundness_data: Dict) -> Dict:
    """
    Identify challenging functions (from generate_insights.py).
    """
    challenging = {
        'no_strategy_correct': [],
        'all_strategies_weak': [],
        'multiple_hallucinations': [],
        'universally_difficult': []
    }

    for task_id in correctness_data.keys():
        # No strategy correct
        if not any(correctness_data[task_id].values()):
            challenging['no_strategy_correct'].append(task_id)

        # All strategies weak
        mutation_scores = [completeness_data[task_id].get(s, 0)
                           for s in ['naive', 'few_shot', 'chain_of_thought']]
        if all(score < 60 for score in mutation_scores):
            challenging['all_strategies_weak'].append({
                'task_id': task_id,
                'scores': dict(zip(['naive', 'few_shot', 'chain_of_thought'], mutation_scores))
            })

        # Multiple hallucinations
        sound_count = sum(soundness_data[task_id].values())
        if sound_count <= 1:
            challenging['multiple_hallucinations'].append(task_id)

        # Universally difficult
        all_fail = (not any(correctness_data[task_id].values()) and
                    all(score < 60 for score in mutation_scores) and
                    sound_count == 0)
        if all_fail:
            challenging['universally_difficult'].append(task_id)

    challenging['no_strategy_correct_count'] = len(challenging['no_strategy_correct'])
    challenging['all_strategies_weak_count'] = len(challenging['all_strategies_weak'])
    challenging['multiple_hallucinations_count'] = len(challenging['multiple_hallucinations'])
    challenging['universally_difficult_count'] = len(challenging['universally_difficult'])

    return challenging


def identify_success_stories(correctness_data: Dict, completeness_data: Dict,
                             soundness_data: Dict) -> Dict:
    """
    Identify success stories (from generate_insights.py).
    """
    success = {
        'all_strategies_correct': [],
        'all_strategies_strong': [],
        'all_strategies_sound': [],
        'perfect_across_board': []
    }

    for task_id in correctness_data.keys():
        if all(correctness_data[task_id].values()):
            success['all_strategies_correct'].append(task_id)

        mutation_scores = [completeness_data[task_id].get(s, 0)
                           for s in ['naive', 'few_shot', 'chain_of_thought']]
        if all(score >= 80 for score in mutation_scores):
            success['all_strategies_strong'].append({
                'task_id': task_id,
                'scores': dict(zip(['naive', 'few_shot', 'chain_of_thought'], mutation_scores))
            })

        if all(soundness_data[task_id].values()):
            success['all_strategies_sound'].append(task_id)

        if (all(correctness_data[task_id].values()) and
                all(score >= 80 for score in mutation_scores) and
                all(soundness_data[task_id].values())):
            success['perfect_across_board'].append(task_id)

    success['all_strategies_correct_count'] = len(success['all_strategies_correct'])
    success['all_strategies_strong_count'] = len(success['all_strategies_strong'])
    success['all_strategies_sound_count'] = len(success['all_strategies_sound'])
    success['perfect_across_board_count'] = len(success['perfect_across_board'])

    return success


def calculate_consistency_metrics(correctness_data: Dict, completeness_data: Dict,
                                  soundness_data: Dict) -> Dict:
    """
    Analyze consistency of each strategy (from generate_insights.py).
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    consistency = {}

    for strategy in strategies:
        correctness_values = [1 if correctness_data[tid].get(strategy, False) else 0
                              for tid in correctness_data.keys()]

        completeness_values = [completeness_data[tid].get(strategy, 0)
                               for tid in completeness_data.keys()]

        soundness_values = [1 if soundness_data[tid].get(strategy, False) else 0
                            for tid in soundness_data.keys()]

        consistency[strategy] = {
            'correctness_variance': round(statistics.variance(correctness_values), 4),
            'completeness_variance': round(statistics.variance(completeness_values), 4),
            'soundness_variance': round(statistics.variance(soundness_values), 4),

            'completeness_coefficient_of_variation': round(
                (statistics.stdev(completeness_values) / statistics.mean(completeness_values) * 100)
                if statistics.mean(completeness_values) > 0 else 0, 2
            ),

            'reliability_score': round(
                statistics.mean(correctness_values) * 0.4 +
                (statistics.mean(completeness_values) / 100) * 0.4 +
                statistics.mean(soundness_values) * 0.2, 4
            )
        }

    return consistency


# Summary Report Generation

def generate_summary_report(all_metrics: Dict) -> str:
    """
    Generate a human-readable summary report (text only).
    """
    lines = []
    lines.append("=" * 80)
    lines.append("COMPREHENSIVE POSTCONDITION EVALUATION ANALYSIS")
    lines.append("Tripartite Evaluation Framework: Correctness, Completeness, Soundness")
    lines.append("=" * 80)
    lines.append("")

    # Overview
    lines.append("### EVALUATION OVERVIEW ###")
    lines.append(f"Total Functions Evaluated: {all_metrics['correctness_metrics']['naive']['total_postconditions']}")
    lines.append("")

    # Correctness
    lines.append("### 1. CORRECTNESS (VALIDITY) - Property-Based Testing ###")
    lines.append("Metric: Percentage of postconditions passing 1000 property-based tests")
    lines.append("")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = all_metrics['correctness_metrics'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Valid Postconditions: {metrics['valid_postconditions']}/{metrics['total_postconditions']}")
        lines.append(f"    Validity Percentage: {metrics['validity_percentage']}%")
        lines.append("")

    # Completeness
    lines.append("### 2. COMPLETENESS (STRENGTH) - Mutation Analysis ###")
    lines.append("Metric: Average Mutation Kill Score (% of mutants detected)")
    lines.append("")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = all_metrics['completeness_metrics'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Average Mutation Kill Score: {metrics['average_mutation_kill_score']}%")
        lines.append(f"    Median Mutation Kill Score: {metrics['median_mutation_kill_score']}%")
        lines.append(f"    Range: {metrics['min_mutation_kill_score']}% - {metrics['max_mutation_kill_score']}%")
        lines.append(f"    High Performers (≥80%): {metrics['high_performers_count']} ({metrics['high_performers_percentage']}%)")
        lines.append(f"    Low Performers (≤40%): {metrics['low_performers_count']} ({metrics['low_performers_percentage']}%)")
        lines.append("")

    # Soundness
    lines.append("### 3. SOUNDNESS (RELIABILITY) - Hallucination Audit ###")
    lines.append("Metric: Percentage of postconditions without hallucinated variables")
    lines.append("")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = all_metrics['soundness_metrics'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Sound Postconditions: {metrics['sound_postconditions']}/{metrics['total_postconditions']}")
        lines.append(f"    Sound Percentage: {metrics['sound_percentage']}%")
        lines.append(f"    Hallucination Rate: {metrics['hallucination_rate']}%")
        lines.append("")

    # Combined
    lines.append("### 4. COMBINED ANALYSIS - Perfect Postconditions ###")
    lines.append("Functions achieving Valid + Strong (≥80%) + Sound simultaneously")
    lines.append("")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = all_metrics['combined_metrics'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Perfect Postconditions: {metrics['perfect_postconditions_count']} ({metrics['perfect_postconditions_percentage']}%)")
        lines.append(f"    Valid + Sound: {metrics['valid_and_sound_count']} ({metrics['valid_and_sound_percentage']}%)")
        lines.append(f"    Valid + Strong: {metrics['valid_and_strong_count']} ({metrics['valid_and_strong_percentage']}%)")
        lines.append(f"    Sound + Strong: {metrics['sound_and_strong_count']} ({metrics['sound_and_strong_percentage']}%)")
        lines.append("")

    # Strategy comparison
    lines.append("### 5. STRATEGY COMPARISON ###")
    lines.append("")
    comp = all_metrics['strategy_comparison']

    lines.append("Rankings:")
    lines.append(f"  Correctness: {' > '.join(comp['correctness_ranking']).replace('_', ' ')}")
    lines.append(f"  Completeness: {' > '.join(comp['completeness_ranking']).replace('_', ' ')}")
    lines.append(f"  Soundness: {' > '.join(comp['soundness_ranking']).replace('_', ' ')}")
    lines.append(f"  Overall: {' > '.join(comp['overall_ranking']).replace('_', ' ')}")
    lines.append("")

    lines.append("Overall Scores (Weighted: 40% Correctness, 40% Completeness, 20% Soundness):")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        lines.append(f"  {strategy.replace('_', ' ').title()}: {comp['overall_scores'][strategy]}")
    lines.append("")

    lines.append(f"BEST OVERALL STRATEGY: {comp['best_overall_strategy'].upper().replace('_', ' ')}")
    lines.append("")

    lines.append("Improvements over Naive Baseline:")
    for strategy in ['few_shot', 'chain_of_thought']:
        improvements = comp['improvements_over_baseline'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Correctness: {improvements['correctness_improvement']:+.2f}%")
        lines.append(f"    Completeness: {improvements['completeness_improvement']:+.2f}%")
        lines.append(f"    Soundness: {improvements['soundness_improvement']:+.2f}%")
        lines.append(f"    Overall: {improvements['overall_improvement']:+.2f}")
        lines.append("")

    # Success stories
    lines.append("### 6. SUCCESS STORIES ###")
    success = all_metrics['success_stories']
    lines.append(f"  Functions where all strategies correct: {success['all_strategies_correct_count']}")
    lines.append(f"  Functions where all strategies strong (≥80%): {success['all_strategies_strong_count']}")
    lines.append(f"  Functions where all strategies sound: {success['all_strategies_sound_count']}")
    lines.append(f"  Functions perfect across all dimensions: {success['perfect_across_board_count']}")
    lines.append("")

    # Challenging functions
    lines.append("### 7. CHALLENGING FUNCTIONS ###")
    challenging = all_metrics['challenging_functions']
    lines.append(f"  Functions where no strategy is correct: {challenging['no_strategy_correct_count']}")
    lines.append(f"  Functions where all strategies weak (<60%): {challenging['all_strategies_weak_count']}")
    lines.append(f"  Functions with multiple hallucinations: {challenging['multiple_hallucinations_count']}")
    lines.append(f"  Functions universally difficult: {challenging['universally_difficult_count']}")
    lines.append("")

    # Consistency
    lines.append("### 8. CONSISTENCY ANALYSIS ###")
    lines.append("Lower variance = More consistent strategy")
    lines.append("")
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = all_metrics['consistency_metrics'][strategy]
        lines.append(f"  {strategy.upper().replace('_', ' ')}:")
        lines.append(f"    Completeness Variance: {metrics['completeness_variance']:.4f}")
        lines.append(f"    Coefficient of Variation: {metrics['completeness_coefficient_of_variation']}%")
        lines.append(f"    Reliability Score: {metrics['reliability_score']:.4f}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF ANALYSIS")
    lines.append("=" * 80)

    return "\n".join(lines)


# Visualization Helper Functions
def set_style():
    """Set consistent style for all plots."""
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 11
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10


def plot_correctness_comparison(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    correctness = data['correctness_metrics']

    percentages = [correctness[s]['validity_percentage'] for s in strategies]
    labels = [STRATEGY_NAMES[s] for s in strategies]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, percentages, color=COLORS, alpha=0.8, edgecolor='black', linewidth=1.5)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax.set_ylabel('Validity Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_title('Correctness (Validity) - Postconditions Passing 1000 Property-Based Tests',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim(0, 100)
    ax.axhline(y=80, color='green', linestyle='--', alpha=0.5, label='80% Threshold')
    ax.legend()

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/correctness_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Correctness comparison chart saved")


def plot_completeness_comparison(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    completeness = data['completeness_metrics']

    avg_scores = [completeness[s]['average_mutation_kill_score'] for s in strategies]
    median_scores = [completeness[s]['median_mutation_kill_score'] for s in strategies]
    labels = [STRATEGY_NAMES[s] for s in strategies]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, avg_scores, width, label='Average',
                   color=COLORS[0], alpha=0.8, edgecolor='black', linewidth=1.5)
    bars2 = ax.bar(x + width / 2, median_scores, width, label='Median',
                   color=COLORS[1], alpha=0.8, edgecolor='black', linewidth=1.5)

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{height:.1f}%',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Mutation Kill Score (%)', fontsize=12, fontweight='bold')
    ax.set_title('Completeness (Strength) - Mutation Analysis Performance',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 110)
    ax.axhline(y=80, color='green', linestyle='--', alpha=0.5, label='80% Threshold')
    ax.legend()

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/completeness_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Completeness comparison chart saved")


def plot_soundness_comparison(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    soundness = data['soundness_metrics']

    sound_pct = [soundness[s]['sound_percentage'] for s in strategies]
    halluc_pct = [soundness[s]['hallucination_rate'] for s in strategies]
    labels = [STRATEGY_NAMES[s] for s in strategies]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Sound
    bars1 = ax1.bar(labels, sound_pct, color=COLORS, alpha=0.8, edgecolor='black', linewidth=1.5)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height:.1f}%',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax1.set_ylabel('Sound Percentage (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Sound Postconditions\n(No Hallucinated Variables)',
                  fontsize=13, fontweight='bold')
    ax1.set_ylim(0, 105)
    ax1.axhline(y=95, color='green', linestyle='--', alpha=0.5, label='95% Threshold')
    ax1.legend()

    # Hallucination
    bars2 = ax2.bar(labels, halluc_pct, color=['#FF6B6B', '#FF6B6B', '#FF6B6B'],
                    alpha=0.6, edgecolor='black', linewidth=1.5)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height:.1f}%',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax2.set_ylabel('Hallucination Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Hallucination Rates\n(Lower is Better)',
                  fontsize=13, fontweight='bold')
    ax2.set_ylim(0, max(halluc_pct) * 1.5 if max(halluc_pct) > 0 else 10)

    plt.suptitle('Soundness (Reliability) - Hallucination Audit Results',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/soundness_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Soundness comparison chart saved")


def plot_mutation_score_distribution(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    completeness = data['completeness_metrics']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    for idx, strategy in enumerate(strategies):
        score_dist = completeness[strategy]['score_distribution']
        ranges = list(score_dist.keys())
        counts = list(score_dist.values())

        axes[idx].bar(ranges, counts, color=COLORS[idx], alpha=0.8,
                      edgecolor='black', linewidth=1.5)
        axes[idx].set_title(STRATEGY_NAMES[strategy], fontsize=13, fontweight='bold')
        axes[idx].set_xlabel('Mutation Kill Score Range', fontsize=11)
        axes[idx].set_ylabel('Number of Functions', fontsize=11)
        axes[idx].tick_params(axis='x', rotation=45)

        for i, (r, c) in enumerate(zip(ranges, counts)):
            axes[idx].text(i, c, str(c), ha='center', va='bottom', fontweight='bold')

    plt.suptitle('Distribution of Mutation Kill Scores by Strategy',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/mutation_score_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Mutation score distribution chart saved")


def plot_combined_metrics_heatmap(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    combined = data['combined_metrics']

    metrics_names = [
        'Perfect (All 3)',
        'Valid + Sound',
        'Valid + Strong',
        'Sound + Strong'
    ]

    matrix = []
    for strategy in strategies:
        row = [
            combined[strategy]['perfect_postconditions_percentage'],
            combined[strategy]['valid_and_sound_percentage'],
            combined[strategy]['valid_and_strong_percentage'],
            combined[strategy]['sound_and_strong_percentage']
        ]
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix, cmap='YlGnBu', aspect='auto', vmin=0, vmax=100)

    ax.set_xticks(np.arange(len(metrics_names)))
    ax.set_yticks(np.arange(len(strategies)))
    ax.set_xticklabels(metrics_names)
    ax.set_yticklabels([STRATEGY_NAMES[s] for s in strategies])

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    for i in range(len(strategies)):
        for j in range(len(metrics_names)):
            ax.text(j, i, f'{matrix[i][j]:.1f}%',
                    ha="center", va="center", color="black", fontweight='bold', fontsize=11)

    ax.set_title('Combined Metrics - Percentage of Functions Meeting Multiple Criteria',
                 fontsize=14, fontweight='bold', pad=20)

    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Percentage (%)', rotation=270, labelpad=20, fontweight='bold')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/combined_metrics_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Combined metrics heatmap saved")


def plot_overall_strategy_comparison(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']

    categories = ['Correctness\n(Validity)', 'Completeness\n(Strength)', 'Soundness\n(Reliability)']
    N = len(categories)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

    for idx, strategy in enumerate(strategies):
        values = [
            data['correctness_metrics'][strategy]['validity_percentage'],
            data['completeness_metrics'][strategy]['average_mutation_kill_score'],
            data['soundness_metrics'][strategy]['sound_percentage']
        ]
        values += values[:1]

        ax.plot(angles, values, 'o-', linewidth=2.5, label=STRATEGY_NAMES[strategy],
                color=COLORS[idx], markersize=8)
        ax.fill(angles, values, alpha=0.15, color=COLORS[idx])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.7)

    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=12, framealpha=0.9)
    plt.title('Strategy Comparison Across Three Evaluation Dimensions\n(Tripartite Framework)',
              fontsize=14, fontweight='bold', pad=30)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/overall_strategy_radar.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Overall strategy radar chart saved")


def plot_success_and_challenge_analysis(data):
    success = data['success_stories']
    challenges = data['challenging_functions']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Success stories
    success_categories = [
        'All Correct',
        'All Strong\n(≥80%)',
        'All Sound',
        'Perfect\n(All 3)'
    ]
    success_counts = [
        success['all_strategies_correct_count'],
        success['all_strategies_strong_count'],
        success['all_strategies_sound_count'],
        success['perfect_across_board_count']
    ]

    bars1 = ax1.bar(success_categories, success_counts,
                    color=['#2ecc71', '#27ae60', '#16a085', '#0a6847'],
                    alpha=0.8, edgecolor='black', linewidth=1.5)

    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax1.set_ylabel('Number of Functions', fontsize=12, fontweight='bold')
    ax1.set_title('Success Stories\n(Functions Where All Strategies Excel)',
                  fontsize=13, fontweight='bold')
    ax1.tick_params(axis='x', rotation=15)

    # Challenging functions
    challenge_categories = [
        'No Strategy\nCorrect',
        'All Weak\n(<60%)',
        'Multiple\nHallucinations',
        'Universally\nDifficult'
    ]
    challenge_counts = [
        challenges['no_strategy_correct_count'],
        challenges['all_strategies_weak_count'],
        challenges['multiple_hallucinations_count'],
        challenges['universally_difficult_count']
    ]

    bars2 = ax2.bar(challenge_categories, challenge_counts,
                    color=['#e74c3c', '#c0392b', '#d35400', '#8b0000'],
                    alpha=0.8, edgecolor='black', linewidth=1.5)

    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax2.set_ylabel('Number of Functions', fontsize=12, fontweight='bold')
    ax2.set_title('Challenging Functions\n(Functions Where All Strategies Struggle)',
                  fontsize=13, fontweight='bold')
    ax2.tick_params(axis='x', rotation=15)

    plt.suptitle('Success vs Challenge Analysis',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/success_challenge_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Success and challenge analysis chart saved")


def plot_improvements_over_baseline(data):
    comparison = data['strategy_comparison']
    improvements = comparison['improvements_over_baseline']

    strategies = ['few_shot', 'chain_of_thought']
    categories = ['Correctness', 'Completeness', 'Soundness', 'Overall']

    few_shot_vals = [
        improvements['few_shot']['correctness_improvement'],
        improvements['few_shot']['completeness_improvement'],
        improvements['few_shot']['soundness_improvement'],
        improvements['few_shot']['overall_improvement']
    ]

    cot_vals = [
        improvements['chain_of_thought']['correctness_improvement'],
        improvements['chain_of_thought']['completeness_improvement'],
        improvements['chain_of_thought']['soundness_improvement'],
        improvements['chain_of_thought']['overall_improvement']
    ]

    x = np.arange(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 7))
    bars1 = ax.bar(x - width / 2, few_shot_vals, width, label='Few-Shot',
                   color=COLORS[0], alpha=0.8, edgecolor='black', linewidth=1.5)
    bars2 = ax.bar(x + width / 2, cot_vals, width, label='Chain-of-Thought',
                   color=COLORS[1], alpha=0.8, edgecolor='black', linewidth=1.5)

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            label = f'{height:+.2f}'
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    label,
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=11, fontweight='bold')

    ax.set_ylabel('Improvement (%)', fontsize=12, fontweight='bold')
    ax.set_title('Improvements Over Naive Baseline\n(Positive = Better Performance)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax.legend(fontsize=12)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/improvements_over_baseline.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Improvements over baseline chart saved")


def plot_consistency_analysis(data):
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    consistency = data['consistency_metrics']

    labels = [STRATEGY_NAMES[s] for s in strategies]
    coef_var = [consistency[s]['completeness_coefficient_of_variation'] for s in strategies]
    reliability = [consistency[s]['reliability_score'] * 100 for s in strategies]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Coefficient of Variation
    bars1 = ax1.bar(labels, coef_var, color=COLORS, alpha=0.8,
                    edgecolor='black', linewidth=1.5)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height:.2f}%',
                 ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax1.set_ylabel('Coefficient of Variation (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Consistency Metric\n(Lower = More Consistent)',
                  fontsize=13, fontweight='bold')
    ax1.set_ylim(0, max(coef_var) * 1.2 if max(coef_var) > 0 else 1)

    # Reliability Score
    bars2 = ax2.bar(labels, reliability, color=COLORS, alpha=0.8,
                    edgecolor='black', linewidth=1.5)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height:.2f}',
                 ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax2.set_ylabel('Reliability Score', fontsize=12, fontweight='bold')
    ax2.set_title('Overall Reliability\n(Higher = More Reliable)',
                  fontsize=13, fontweight='bold')
    ax2.set_ylim(0, 100)

    plt.suptitle('Consistency and Reliability Analysis',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/consistency_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Consistency analysis chart saved")


def plot_overall_scores_ranking(data):
    comparison = data['strategy_comparison']
    strategies_ordered = comparison['overall_ranking']

    scores = [comparison['overall_scores'][s] for s in strategies_ordered]
    labels = [STRATEGY_NAMES[s] for s in strategies_ordered]
    colors_ordered = [COLORS[['naive', 'few_shot', 'chain_of_thought'].index(s)]
                      for s in strategies_ordered]

    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(labels, scores, color=colors_ordered, alpha=0.8,
                   edgecolor='black', linewidth=2)

    for i, (bar, score) in enumerate(zip(bars, scores)):
        width = bar.get_width()
        rank = i + 1
        label = f'#{rank} - {score:.2f}'
        ax.text(width + 1, bar.get_y() + bar.get_height() / 2.,
                label,
                ha='left', va='center', fontsize=13, fontweight='bold')

    ax.set_xlabel('Overall Score (Weighted Average)', fontsize=12, fontweight='bold')
    ax.set_title('Overall Strategy Rankings\n(40% Correctness + 40% Completeness + 20% Soundness)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlim(0, 100)
    ax.grid(axis='x', alpha=0.3)

    best = comparison['best_overall_strategy']
    ax.text(0.95, 0.95, f'Best Overall:\n{STRATEGY_NAMES[best]}',
            transform=ax.transAxes,
            fontsize=13, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='gold', alpha=0.8),
            ha='right', va='top')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/overall_scores_ranking.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Overall scores ranking chart saved")


def create_summary_dashboard(data):
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    strategies = ['naive', 'few_shot', 'chain_of_thought']
    strategy_labels = [STRATEGY_NAMES[s] for s in strategies]

    # 1. Correctness
    ax1 = fig.add_subplot(gs[0, 0])
    correctness = [data['correctness_metrics'][s]['validity_percentage'] for s in strategies]
    ax1.bar(strategy_labels, correctness, color=COLORS, alpha=0.8, edgecolor='black')
    ax1.set_title('Correctness (Validity %)', fontweight='bold')
    ax1.set_ylim(0, 100)
    for i, v in enumerate(correctness):
        ax1.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')

    # 2. Completeness
    ax2 = fig.add_subplot(gs[0, 1])
    completeness = [data['completeness_metrics'][s]['average_mutation_kill_score'] for s in strategies]
    ax2.bar(strategy_labels, completeness, color=COLORS, alpha=0.8, edgecolor='black')
    ax2.set_title('Completeness (Avg Mutation %)', fontweight='bold')
    ax2.set_ylim(0, 100)
    for i, v in enumerate(completeness):
        ax2.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')

    # 3. Soundness
    ax3 = fig.add_subplot(gs[0, 2])
    soundness = [data['soundness_metrics'][s]['sound_percentage'] for s in strategies]
    ax3.bar(strategy_labels, soundness, color=COLORS, alpha=0.8, edgecolor='black')
    ax3.set_title('Soundness (No Hallucination %)', fontweight='bold')
    ax3.set_ylim(0, 100)
    for i, v in enumerate(soundness):
        ax3.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')

    # 4. Perfect Postconditions
    ax4 = fig.add_subplot(gs[1, 0])
    perfect = [data['combined_metrics'][s]['perfect_postconditions_percentage'] for s in strategies]
    ax4.bar(strategy_labels, perfect, color=COLORS, alpha=0.8, edgecolor='black')
    ax4.set_title('Perfect Postconditions %', fontweight='bold')
    ax4.set_ylim(0, 100)
    for i, v in enumerate(perfect):
        ax4.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')

    # 5. High Performers
    ax5 = fig.add_subplot(gs[1, 1])
    high_perf = [data['completeness_metrics'][s]['high_performers_percentage'] for s in strategies]
    ax5.bar(strategy_labels, high_perf, color=COLORS, alpha=0.8, edgecolor='black')
    ax5.set_title('High Performers (≥80%) %', fontweight='bold')
    ax5.set_ylim(0, 100)
    for i, v in enumerate(high_perf):
        ax5.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')

    # 6. Overall Score
    ax6 = fig.add_subplot(gs[1, 2])
    overall = [data['strategy_comparison']['overall_scores'][s] for s in strategies]
    ax6.bar(strategy_labels, overall, color=COLORS, alpha=0.8, edgecolor='black')
    ax6.set_title('Overall Weighted Score', fontweight='bold')
    ax6.set_ylim(0, 100)
    for i, v in enumerate(overall):
        ax6.text(i, v, f'{v:.2f}', ha='center', va='bottom', fontweight='bold')

    # 7. Success Stories
    ax7 = fig.add_subplot(gs[2, 0])
    success = data['success_stories']
    success_counts = [
        success['perfect_across_board_count'],
        success['all_strategies_correct_count'],
        success['all_strategies_strong_count'],
        success['all_strategies_sound_count']
    ]
    success_labels = ['Perfect\nAll 3', 'All\nCorrect', 'All\nStrong', 'All\nSound']
    ax7.bar(success_labels, success_counts,
            color=['#2ecc71', '#27ae60', '#16a085', '#0a6847'],
            alpha=0.8, edgecolor='black')
    ax7.set_title('Success Stories (Count)', fontweight='bold')
    ax7.tick_params(axis='x', labelsize=9)
    for i, v in enumerate(success_counts):
        ax7.text(i, v, str(v), ha='center', va='bottom', fontweight='bold')

    # 8. Challenging Functions
    ax8 = fig.add_subplot(gs[2, 1])
    challenges = data['challenging_functions']
    challenge_counts = [
        challenges['no_strategy_correct_count'],
        challenges['all_strategies_weak_count'],
        challenges['multiple_hallucinations_count'],
        challenges['universally_difficult_count']
    ]
    challenge_labels = ['No\nCorrect', 'All\nWeak', 'Multi\nHalluc', 'Univ.\nDiff']
    ax8.bar(challenge_labels, challenge_counts,
            color=['#e74c3c', '#c0392b', '#d35400', '#8b0000'],
            alpha=0.8, edgecolor='black')
    ax8.set_title('Challenging Functions (Count)', fontweight='bold')
    ax8.tick_params(axis='x', labelsize=9)
    for i, v in enumerate(challenge_counts):
        ax8.text(i, v, str(v), ha='center', va='bottom', fontweight='bold')

    # 9. Key statistics text
    ax9 = fig.add_subplot(gs[2, 2])
    ax9.axis('off')

    best_strategy = data['strategy_comparison']['best_overall_strategy']
    total_funcs = data['correctness_metrics']['naive']['total_postconditions']

    stats_text = f"""
KEY STATISTICS

Total Functions: {total_funcs}

Best Overall Strategy:
  {STRATEGY_NAMES[best_strategy]}

Top Correctness:
  {STRATEGY_NAMES[data['strategy_comparison']['correctness_ranking'][0]]}

Top Completeness:
  {STRATEGY_NAMES[data['strategy_comparison']['completeness_ranking'][0]]}

Top Soundness:
  {STRATEGY_NAMES[data['strategy_comparison']['soundness_ranking'][0]]}
"""

    ax9.text(0.1, 0.5, stats_text, fontsize=11, fontweight='bold',
             verticalalignment='center', family='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.suptitle('Postcondition Evaluation Dashboard - Tripartite Framework Summary',
                 fontsize=16, fontweight='bold', y=0.98)

    plt.savefig(f'{OUTPUT_DIR}/comprehensive_dashboard.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Comprehensive dashboard saved")


# Quick Summary Function

def print_quick_summary(data):
    """Print a quick, formatted summary."""
    print("\n" + "=" * 80)
    print(" 🎯 POSTCONDITION EVALUATION - QUICK SUMMARY")
    print("=" * 80 + "\n")

    total = data['correctness_metrics']['naive']['total_postconditions']
    print(f"📊 Total Functions Evaluated: {total}\n")

    # Best overall strategy
    best = data['strategy_comparison']['best_overall_strategy']
    best_display = best.replace('_', ' ').title()
    print(f"🏆 Best Overall Strategy: {best_display}\n")

    print("-" * 80)
    print("1️⃣  CORRECTNESS (Validity - Property-Based Testing)")
    print("-" * 80)
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = data['correctness_metrics'][strategy]
        name = strategy.replace('_', ' ').title().ljust(20)
        valid = metrics['valid_postconditions']
        pct = metrics['validity_percentage']
        print(f"   {name}: {valid}/{total} valid ({pct:.1f}%)")

    print("\n" + "-" * 80)
    print("2️⃣  COMPLETENESS (Strength - Mutation Analysis)")
    print("-" * 80)
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = data['completeness_metrics'][strategy]
        name = strategy.replace('_', ' ').title().ljust(20)
        avg = metrics['average_mutation_kill_score']
        high = metrics['high_performers_count']
        print(f"   {name}: {avg:.1f}% avg kill score, {high} high performers (≥80%)")

    print("\n" + "-" * 80)
    print("3️⃣  SOUNDNESS (Reliability - Hallucination Audit)")
    print("-" * 80)
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = data['soundness_metrics'][strategy]
        name = strategy.replace('_', ' ').title().ljust(20)
        sound = metrics['sound_postconditions']
        pct = metrics['sound_percentage']
        h_rate = metrics['hallucination_rate']
        print(f"   {name}: {sound}/{total} sound ({pct:.1f}%), {h_rate:.1f}% hallucination rate")

    print("\n" + "-" * 80)
    print("4️⃣  PERFECT POSTCONDITIONS (Valid + Strong + Sound)")
    print("-" * 80)
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = data['combined_metrics'][strategy]
        name = strategy.replace('_', ' ').title().ljust(20)
        perfect = metrics['perfect_postconditions_count']
        pct = metrics['perfect_postconditions_percentage']
        print(f"   {name}: {perfect}/{total} perfect ({pct:.1f}%)")

    print("\n" + "-" * 80)
    print("5️⃣  OVERALL WEIGHTED SCORES (40% Correct + 40% Complete + 20% Sound)")
    print("-" * 80)
    scores = data['strategy_comparison']['overall_scores']
    ranking = data['strategy_comparison']['overall_ranking']

    for rank, strategy in enumerate(ranking, 1):
        name = strategy.replace('_', ' ').title().ljust(20)
        score = scores[strategy]
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
        print(f"   {medal} #{rank} {name}: {score:.2f}")

    print("\n" + "-" * 80)
    print("6️⃣  IMPROVEMENTS OVER NAIVE BASELINE")
    print("-" * 80)
    improvements = data['strategy_comparison']['improvements_over_baseline']

    for strategy in ['few_shot', 'chain_of_thought']:
        name = strategy.replace('_', ' ').title()
        imp = improvements[strategy]
        corr = imp['correctness_improvement']
        comp = imp['completeness_improvement']
        sound = imp['soundness_improvement']
        overall = imp['overall_improvement']

        print(f"\n   {name}:")
        print(f"      Correctness:  {corr:+.2f}%")
        print(f"      Completeness: {comp:+.2f}%")
        print(f"      Soundness:    {sound:+.2f}%")
        print(f"      Overall:      {overall:+.2f}")

    print("\n" + "-" * 80)
    print("7️⃣  SUCCESS STORIES & CHALLENGES")
    print("-" * 80)
    success = data['success_stories']
    challenges = data['challenging_functions']

    print(f"\n   ✅ Success Stories:")
    print(f"      • {success['perfect_across_board_count']} functions perfect across all dimensions")
    print(f"      • {success['all_strategies_correct_count']} functions where all strategies are correct")
    print(f"      • {success['all_strategies_strong_count']} functions where all strategies are strong (≥80%)")
    print(f"      • {success['all_strategies_sound_count']} functions where all strategies are sound")

    print(f"\n   🔧  Challenges:")
    print(f"      • {challenges['no_strategy_correct_count']} functions where no strategy is correct")
    print(f"      • {challenges['all_strategies_weak_count']} functions where all strategies are weak (<60%)")
    print(f"      • {challenges['multiple_hallucinations_count']} functions with multiple hallucinations")
    print(f"      • {challenges['universally_difficult_count']} functions universally difficult")

    print("\n" + "-" * 80)
    print("8️⃣  CONSISTENCY & RELIABILITY")
    print("-" * 80)
    for strategy in ['naive', 'few_shot', 'chain_of_thought']:
        metrics = data['consistency_metrics'][strategy]
        name = strategy.replace('_', ' ').title().ljust(20)
        cv = metrics['completeness_coefficient_of_variation']
        rel = metrics['reliability_score']
        print(f"   {name}: CV={cv:.2f}%, Reliability={rel:.4f}")

    print("\n" + "=" * 80)
    print(" 📈 Detailed analysis has been written to: src/reports/analysis_summary.txt")
    print(" 📊 Visualizations have been saved to:   src/reports/visualizations/")
    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("POSTCONDITION EVALUATION ANALYSIS + VISUALIZATION")
    print("=" * 80)
    print()

    # Load reports
    print("Loading evaluation reports...")
    correctness_data, completeness_data, soundness_data = load_reports()
    print(f"✓ Loaded data for {len(correctness_data)} functions")
    print()

    # Calculate metrics
    print("Calculating metrics...")
    print("  1. Correctness (Validity) metrics...")
    correctness_metrics = calculate_correctness_metrics(correctness_data)

    print("  2. Completeness (Strength) metrics...")
    completeness_metrics = calculate_completeness_metrics(completeness_data)

    print("  3. Soundness (Reliability) metrics...")
    soundness_metrics = calculate_soundness_metrics(soundness_data)

    print("  4. Combined metrics...")
    combined_metrics = calculate_combined_metrics(correctness_data, completeness_data, soundness_data)

    print("  5. Strategy comparison...")
    strategy_comparison = calculate_strategy_comparison(correctness_metrics, completeness_metrics, soundness_metrics)

    print("  6. Challenging functions analysis...")
    challenging_functions = identify_challenging_functions(correctness_data, completeness_data, soundness_data)

    print("  7. Success stories analysis...")
    success_stories = identify_success_stories(correctness_data, completeness_data, soundness_data)

    print("  8. Consistency metrics...")
    consistency_metrics = calculate_consistency_metrics(correctness_data, completeness_data, soundness_data)

    print("✓ All metrics calculated")
    print()

    # Combine metrics into a single in-memory structure
    all_metrics = {
        'correctness_metrics': correctness_metrics,
        'completeness_metrics': completeness_metrics,
        'soundness_metrics': soundness_metrics,
        'combined_metrics': combined_metrics,
        'strategy_comparison': strategy_comparison,
        'challenging_functions': challenging_functions,
        'success_stories': success_stories,
        'consistency_metrics': consistency_metrics
    }

    # Generate and save summary report (only text, no JSON)
    print(f"Generating summary report to {SUMMARY_FILE}...")
    summary = generate_summary_report(all_metrics)
    Path(Path(SUMMARY_FILE).parent).mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_FILE, 'w') as f:
        f.write(summary)
    print("✓ Summary report saved")
    print()

    # Visualizations
    print("Generating visualizations...")
    set_style()
    plot_correctness_comparison(all_metrics)
    plot_completeness_comparison(all_metrics)
    plot_soundness_comparison(all_metrics)
    plot_mutation_score_distribution(all_metrics)
    plot_combined_metrics_heatmap(all_metrics)
    plot_overall_strategy_comparison(all_metrics)
    plot_success_and_challenge_analysis(all_metrics)
    plot_improvements_over_baseline(all_metrics)
    plot_consistency_analysis(all_metrics)
    plot_overall_scores_ranking(all_metrics)
    create_summary_dashboard(all_metrics)

    print()
    print("=" * 80)
    print(f"✓ All visualizations saved to: {OUTPUT_DIR}/")
    print("=" * 80)
    print()

    # Quick console summary
    print_quick_summary(all_metrics)


if __name__ == "__main__":
    main()
