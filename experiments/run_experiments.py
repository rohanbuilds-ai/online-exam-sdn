#!/usr/bin/env python3
"""
Master Experiment Orchestrator for SDN Online Examination Network.

Executes:
1. Baseline (Static SDN) performance benchmark under normal and congested traffic.
2. Dynamic SDN (Adaptive QoS) performance benchmark with automatic prioritization.
3. Statistical comparative analysis, Jain's fairness index evaluation, and chart generation.
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.baseline import run_baseline_benchmark
from experiments.dynamic_sdn import run_dynamic_sdn_benchmark
from experiments.analyze_results import generate_analysis_report


def main():
    print("=" * 75)
    print("   SDN ONLINE EXAMINATION NETWORK - MASTER EXPERIMENT SUITE")
    print("=" * 75)
    t0 = time.time()

    # 1. Run Baseline (Static SDN)
    print("\n[PHASE 1] Executing Baseline Benchmark (Static SDN)...")
    run_baseline_benchmark(concurrency_levels=[5, 10, 20])

    # 2. Run Dynamic SDN (Adaptive QoS)
    print("\n[PHASE 2] Executing Dynamic SDN Benchmark (Adaptive QoS Prioritization)...")
    run_dynamic_sdn_benchmark(concurrency_levels=[5, 10, 20])

    # 3. Analyze Results and Generate Charts
    print("\n[PHASE 3] Generating Comparative Analytics, Markdown Report, and Charts...")
    generate_analysis_report()

    elapsed = time.time() - t0
    print("\n" + "=" * 75)
    print(f"   EXPERIMENT SUITE COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS")
    print("   Artifacts generated in results/:")
    print("     - results/baseline_results.csv")
    print("     - results/dynamic_sdn_results.csv")
    print("     - results/performance_comparison.md")
    print("     - results/latency_comparison.png")
    print("     - results/throughput_fairness_comparison.png")
    print("=" * 75)


if __name__ == "__main__":
    main()
