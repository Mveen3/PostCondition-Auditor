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
import matplotlib.gridspec as gridspec
import numpy as np


# Input report files
CORRECTNESS_REPORT = "src/reports/correctness_report.json"
COMPLETENESS_REPORT = "src/reports/completeness_report.json"
SOUNDNESS_REPORT = "src/reports/soundness_report.json"

# Outputs
SUMMARY_FILE = "src/reports/analysis_summary.txt"
DASHBOARD_FILE = "src/reports/dashboard.png"

# Visualization config
STRATEGY_NAMES = {
    'naive': 'Naive',
    'few_shot': 'Few Shot',
    'chain_of_thought': 'Chain of Thought'
}


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
    Identify challenging functions.
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
    Identify success stories.
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
    Analyze consistency of each strategy.
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
    Generate a human-readable summary report.
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


# COMPREHENSIVE DASHBOARD VISUALIZATION

def create_comprehensive_dashboard(data: Dict) -> None:
    """
    Generates comprehensive dashboard with all evaluation metrics.
    """
    strategies = ['naive', 'few_shot', 'chain_of_thought']
    strategy_labels = [STRATEGY_NAMES[s] for s in strategies]
    
    # 1. DATA EXTRACTION FROM COMPUTED METRICS
        
    # COLORS FOR CHART 1 (Core Metrics)
    metric_colors = ['#FF4D4D', '#33B5E5', '#FFA500']  # Red, Sky Blue, Orange
    
    # Strategy colors for other charts
    strategy_colors_dark = ['#CC4444', '#008080', '#CC9900']
    
    bar_width = 0.25
    
    # Metric 1: Core Percentages
    correctness_pcts = [data['correctness_metrics'][s]['validity_percentage'] for s in strategies]
    completeness_pcts = [data['completeness_metrics'][s]['average_mutation_kill_score'] for s in strategies]
    soundness_pcts = [data['soundness_metrics'][s]['sound_percentage'] for s in strategies]
    
    metrics_core = {
        'Correctness (% of Postconditions Passing All 1000 Test Cases)': correctness_pcts,
        'Completeness (Avg % of Mutants Killed by Postconditions out of 5 Mutants)': completeness_pcts,
        'Soundness (% of Postconditions with No Hallucination)': soundness_pcts
    }
    
    # Metric 2: High/Low Performers
    comp_high = [data['completeness_metrics'][s]['high_performers_count'] for s in strategies]
    comp_low = [data['completeness_metrics'][s]['low_performers_count'] for s in strategies]
    
    # Metric 3: Combined Analysis for HEATMAP
    combined_keys = ['Perfect (All 3)', 'Valid + Sound', 'Valid + Strong', 'Sound + Strong']
    combined_data_raw = {
        'Perfect (All 3)': [data['combined_metrics'][s]['perfect_postconditions_count'] for s in strategies],
        'Valid + Sound': [data['combined_metrics'][s]['valid_and_sound_count'] for s in strategies],
        'Valid + Strong': [data['combined_metrics'][s]['valid_and_strong_count'] for s in strategies],
        'Sound + Strong': [data['combined_metrics'][s]['sound_and_strong_count'] for s in strategies]
    }
    
    total_functions = data['correctness_metrics']['naive']['total_postconditions']
    
    # Metric 4: Overall Scores
    overall_scores = [data['strategy_comparison']['overall_scores'][s] for s in strategies]
    
    # Metric 5: Improvements
    improvements = {
        'Correctness': [0, 
                        data['strategy_comparison']['improvements_over_baseline']['few_shot']['correctness_improvement'],
                        data['strategy_comparison']['improvements_over_baseline']['chain_of_thought']['correctness_improvement']],
        'Completeness': [0,
                         data['strategy_comparison']['improvements_over_baseline']['few_shot']['completeness_improvement'],
                         data['strategy_comparison']['improvements_over_baseline']['chain_of_thought']['completeness_improvement']],
        'Soundness': [0,
                      data['strategy_comparison']['improvements_over_baseline']['few_shot']['soundness_improvement'],
                      data['strategy_comparison']['improvements_over_baseline']['chain_of_thought']['soundness_improvement']],
        'Overall Score': [0,
                          data['strategy_comparison']['improvements_over_baseline']['few_shot']['overall_improvement'],
                          data['strategy_comparison']['improvements_over_baseline']['chain_of_thought']['overall_improvement']]
    }
    
    # Metric 6: Consistency
    consistency_cv = [data['consistency_metrics'][s]['completeness_coefficient_of_variation'] for s in strategies]
    
    # Metric 7: Summary Table
    success = data['success_stories']
    challenges = data['challenging_functions']
    summary_counts = [
        ("Functions where all strategies correct", str(success['all_strategies_correct_count'])),
        ("Functions where all strategies strong", str(success['all_strategies_strong_count'])),
        ("Functions where all strategies sound", str(success['all_strategies_sound_count'])),
        ("Functions perfect across all dimensions", str(success['perfect_across_board_count'])),
        ("Functions where no strategy is correct", str(challenges['no_strategy_correct_count'])),
        ("Functions where all strategies weak", str(challenges['all_strategies_weak_count'])),
        ("Functions with multiple hallucinations", str(challenges['multiple_hallucinations_count']))
    ]
    
    # 2. PLOTTING SETUP
    
    plt.style.use('default')
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['text.color'] = 'black'
    
    fig = plt.figure(figsize=(20, 20), facecolor='white')
    
    fig.suptitle('COMPREHENSIVE POSTCONDITION EVALUATION ANALYSIS\nTripartite Framework: Correctness, Completeness, Soundness', 
                 fontsize=26, fontweight='bold', color='#1a1a2e', y=1)
    
    # Grid Layout
    gs = gridspec.GridSpec(5, 2, height_ratios=[0.8, 0.8, 0.9, 0.8, 0.7], hspace=0.55, wspace=0.25)
    
    # CHART 1: The Big Three (Core Metrics)
    ax1 = fig.add_subplot(gs[0, :])
    x = np.arange(len(strategy_labels))
    metric_keys = list(metrics_core.keys())
    offsets = [-bar_width, 0, bar_width]
    
    for i, key in enumerate(metric_keys):
        bars = ax1.bar(x + offsets[i], metrics_core[key], width=bar_width, 
                       label=key, color=metric_colors[i], edgecolor='black')
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1, f'{height}%', 
                     ha='center', va='bottom', fontsize=12, fontweight='bold', color='#1a1a2e')
    
    ax1.legend(loc='upper left', fontsize=9, framealpha=0.9, facecolor='white', edgecolor='gray')
    ax1.set_title('CORE METRICS COMPARISON (Validity, Strength, Reliability)', fontsize=18, color='#006666', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(strategy_labels, fontsize=14)
    ax1.set_ylim(80, 110)
    ax1.set_ylabel('Percentage (%)', fontsize=12)
    ax1.grid(axis='y', alpha=0.1, linestyle='--')
    
    # CHART 2: Completeness Deep Dive
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.bar(strategy_labels, comp_high, width=0.4, label='High Performers (≥80% ie 4 or More Mutants Killed out of 5 Mutants)', color='#99FF99', edgecolor='black')
    ax2.bar(strategy_labels, comp_low, width=0.4, bottom=comp_high, label='Low Performers (≤40% ie 2 or Fewer Mutants Killed out of 5 Mutants)', color='#FF4D4D', edgecolor='black')
    
    for i, v in enumerate(comp_high):
        ax2.text(i, v/2, str(v), ha='center', color='black', fontweight='bold', fontsize=12)
    for i, v in enumerate(comp_low):
        if v > 0: 
            ax2.text(i, v + comp_high[i] + 1, str(v), ha='center', color='black', fontweight='bold', fontsize=12)
    
    ax2.set_title('COMPLETENESS STRENGTH\n(High vs Low Performers)', fontsize=16, color='#006666', pad=10)
    ax2.legend(loc='upper center', framealpha=0.9, facecolor='white', edgecolor='gray')
    ax2.set_ylabel('Number of Postconditions', fontsize=12)
    
    # CHART 3: Consistency
    ax3 = fig.add_subplot(gs[1, 1])
    bars = ax3.bar(strategy_labels, consistency_cv, color=strategy_colors_dark, width=0.5, edgecolor='black')
    ax3.set_title('CONSISTENCY ANALYSIS\n(Coefficient of Variation of Mutation Kill Rates: 5 Mutants/Function -> Lower = More Reliable)', fontsize=16, color='#006666', pad=10)
    for bar in bars:
        ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5, f'{bar.get_height()}%', 
                 ha='center', va='bottom', color="#1a1a2e", fontweight='bold', fontsize=12)
    ax3.set_ylabel('Percentage (%)', fontsize=12)
    
    # CHART 4: HEATMAP (High Contrast)
    ax4 = fig.add_subplot(gs[2, :])
    
    # Prepare Data
    heatmap_data = np.zeros((3, 4))
    for col_idx, key in enumerate(combined_keys):
        values = combined_data_raw[key]
        for row_idx, val in enumerate(values):
            heatmap_data[row_idx, col_idx] = (val / float(total_functions)) * 100.0
    
    # PLOT: Using 'RdYlGn' (Red-Yellow-Green) for maximum contrast
    im = ax4.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=75, vmax=95)
    
    # Annotations with Dynamic Text Color
    for i in range(3): 
        for j in range(4): 
            pct = heatmap_data[i, j]
            count = int((pct/100) * total_functions)
            label = f"{pct:.1f}%\n({count}/{total_functions})"
            ax4.text(j, i, label, ha="center", va="center", color='black', fontweight='bold', fontsize=14)
    
    ax4.set_xticks(np.arange(len(combined_keys)))
    ax4.set_yticks(np.arange(len(strategy_labels)))
    ax4.set_xticklabels(combined_keys, fontsize=13, weight='bold', color='black')
    ax4.set_yticklabels(strategy_labels, fontsize=13, weight='bold', color='black')
    ax4.set_title('COMBINED METRICS HEATMAP (% of Functions Meeting Criteria)', fontsize=18, color='#006666', pad=15)
    
    for edge, spine in ax4.spines.items():
        spine.set_visible(False)
    
    ax4.set_xticks(np.arange(len(combined_keys)+1)-.5, minor=True)
    ax4.set_yticks(np.arange(len(strategy_labels)+1)-.5, minor=True)
    ax4.grid(which="minor", color="black", linestyle='-', linewidth=2)
    ax4.tick_params(which="minor", bottom=False, left=False)
    
    # CHART 5: Overall Score
    ax5 = fig.add_subplot(gs[3, 0])
    bars = ax5.bar(strategy_labels, overall_scores, color=strategy_colors_dark, width=0.5, edgecolor='black')
    ax5.set_ylim(90, 96)
    ax5.set_title('OVERALL WEIGHTED SCORE\n(40% Corr, 40% Comp, 20% Sound)', fontsize=16, color='#006666', pad=10)
    for bar in bars:
        ax5.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1, str(round(bar.get_height(), 2)), 
                 ha='center', fontweight='bold', fontsize=12, color='#1a1a2e')
    ax5.set_ylabel('Percentage (%)', fontsize=12)
    
    # CHART 6: Improvements
    ax6 = fig.add_subplot(gs[3, 1])
    y_pos = np.arange(len(improvements.keys()))
    fs_vals = [improvements[k][1] for k in improvements]
    cot_vals = [improvements[k][2] for k in improvements]
    
    ax6.barh(y_pos + 0.2, fs_vals, height=0.4, label='Few Shot Delta', color='#008080', edgecolor='black')
    ax6.barh(y_pos - 0.2, cot_vals, height=0.4, label='CoT Delta', color='#CC9900', edgecolor='black')
    ax6.set_yticks(y_pos)
    ax6.set_yticklabels(improvements.keys(), fontsize=12, color='black')
    ax6.axvline(0, color='black', linewidth=1)
    ax6.legend(loc='lower right', framealpha=0.9, facecolor='white', edgecolor='gray')
    ax6.set_title('IMPROVEMENT VS BASELINE', fontsize=16, color='#006666', pad=10)
    ax6.set_xlabel('Percentage (%)', fontsize=12)
    
    # CHART 7: Summary Table
    ax7 = fig.add_subplot(gs[4, :])
    ax7.axis('off')
    table_data = [[k, v] for k, v in summary_counts]
    
    table = ax7.table(cellText=table_data, colLabels=["Metric Category", "Count"], 
                      loc='center', cellLoc='center', colColours=['#006666', '#006666'])
    table.auto_set_font_size(False)
    table.set_fontsize(13)
    table.scale(1, 1.8)
    
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white', fontsize=14)
        else:
            cell.set_text_props(color='black')
        cell.set_edgecolor('#999')
        if row > 0: 
            cell.set_facecolor('#f5f5f5')
    
    ax7.set_title("SUCCESS STORIES & CHALLENGES SUMMARY", fontsize=16, color='#006666', pad=35)
    
    plt.subplots_adjust(top=0.92, bottom=0.02, left=0.05, right=0.95, hspace=0.45, wspace=0.25)
    plt.savefig(DASHBOARD_FILE, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print(f"✓ Comprehensive dashboard saved to: {DASHBOARD_FILE}")


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
    print(f" 📈 Detailed analysis has been written to: {SUMMARY_FILE}")
    print(f" 📊 Dashboard has been saved to: {DASHBOARD_FILE}")
    print("=" * 80 + "\n")


# Main Orchestration

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

    # Generate and save summary report
    print(f"Generating summary report to {SUMMARY_FILE}...")
    summary = generate_summary_report(all_metrics)
    Path(Path(SUMMARY_FILE).parent).mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_FILE, 'w') as f:
        f.write(summary)
    print("✓ Summary report saved")
    print()

    # Generate comprehensive dashboard
    print("Generating comprehensive dashboard...")
    create_comprehensive_dashboard(all_metrics)

    print()
    print("=" * 80)
    print(f"✓ Summary report saved to: {SUMMARY_FILE}")
    print(f"✓ Dashboard saved to: {DASHBOARD_FILE}")
    print("=" * 80)
    print()

    # Quick console summary
    print_quick_summary(all_metrics)


if __name__ == "__main__":
    main()
