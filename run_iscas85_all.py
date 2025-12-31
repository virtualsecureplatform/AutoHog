#!/usr/bin/env python3
"""
Script to run AutoHog synthesis on all ISCAS85 benchmark circuits
and report the synthesized gate counts.
"""

import subprocess
import os
import sys
import shutil
import re
import json
import time
from datetime import datetime

# All ISCAS85 benchmark circuits
ISCAS85_CIRCUITS = [
    'c17', 'c432', 'c499', 'c880', 'c1355',
    'c1908', 'c2670', 'c3540', 'c5315', 'c6288', 'c7552'
]

# Paths
AUTOHOG_DIR = os.path.dirname(os.path.abspath(__file__))
VERILOG_DIR = os.path.join(AUTOHOG_DIR, 'Verilog_file')
EXACT_SYNTH_DIR = os.path.join(AUTOHOG_DIR, '..', 'ExactTFHEsynth', 'test', 'iscas85')


def copy_missing_verilog_files():
    """Copy missing verilog files from ExactTFHEsynth repository."""
    copied = []
    for circuit in ISCAS85_CIRCUITS:
        dest_file = os.path.join(VERILOG_DIR, f'{circuit}.v')
        if not os.path.exists(dest_file):
            # Look for the verilog file in ExactTFHEsynth
            src_file = os.path.join(EXACT_SYNTH_DIR, circuit, 'verilog', f'{circuit}.v')
            if os.path.exists(src_file):
                shutil.copy(src_file, dest_file)
                copied.append(circuit)
                print(f"Copied: {circuit}.v from ExactTFHEsynth")
            else:
                print(f"Warning: Could not find {circuit}.v in ExactTFHEsynth")
    return copied


def run_synthesis(circuit_name):
    """
    Run synthesis on a single circuit and return gate counts and time.
    Returns (original_count, optimized_count, synth_time) or (None, None, None) on failure.
    """
    print(f"\n{'='*60}")
    print(f"Processing: {circuit_name}")
    print('='*60)

    # Check if verilog file exists
    verilog_file = os.path.join(VERILOG_DIR, f'{circuit_name}.v')
    if not os.path.exists(verilog_file):
        print(f"Error: {verilog_file} not found")
        return None, None, None

    # Start timing
    start_time = time.time()

    # Run yosys to generate netlist
    template_file = os.path.join(AUTOHOG_DIR, 'build_template.ys')
    output_file = os.path.join(AUTOHOG_DIR, 'build.ys')

    with open(template_file, 'r') as f:
        template = f.read()

    ys_content = template.replace("{filename}", f"Verilog_file/{circuit_name}")
    with open(output_file, 'w') as f:
        f.write(ys_content)

    print("Running Yosys...")
    # Use system yosys if available, otherwise try thirdparties
    yosys_path = shutil.which('yosys')
    if yosys_path is None:
        yosys_path = os.path.join(AUTOHOG_DIR, 'thirdparties', 'yosys', 'yosys')
    result = subprocess.run(
        [yosys_path, output_file],
        cwd=AUTOHOG_DIR,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Yosys failed for {circuit_name}")
        print(result.stderr)
        return None, None, None

    # Load config
    config_path = os.path.join(AUTOHOG_DIR, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    searchnum_up = config.get('searchnum_up', 32)
    searchnum_low = config.get('searchnum_low', 5)
    replace_num = config.get('replace_num', 3)

    # Run search_replace.py to optimize
    print("Running optimization...")
    result = subprocess.run(
        ['python3', 'search_replace.py', circuit_name,
         str(searchnum_up), str(searchnum_low), str(replace_num)],
        cwd=AUTOHOG_DIR,
        capture_output=True,
        text=True
    )

    output = result.stdout + result.stderr
    print(output)

    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    # Parse gate counts from output
    original_match = re.search(r'Original gate num:\s*(\d+)', output)
    optimized_match = re.search(r'Optimized gate num:\s*(\d+)', output)

    original_count = int(original_match.group(1)) if original_match else None
    optimized_count = int(optimized_match.group(1)) if optimized_match else None

    print(f"Synthesis time: {elapsed_time:.2f}s")

    return original_count, optimized_count, elapsed_time


def main():
    # Create timestamp for output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(AUTOHOG_DIR, f'iscas85_synthesis_{timestamp}.log')

    # Open log file for writing
    with open(log_file, 'w') as log:
        def log_print(msg=""):
            """Print to both console and log file."""
            print(msg)
            log.write(msg + "\n")
            log.flush()

        log_print("="*60)
        log_print("AutoHog ISCAS85 Benchmark Synthesis")
        log_print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_print("="*60)

        # Step 1: Copy missing verilog files
        log_print("\n[Step 1] Checking and copying missing verilog files...")
        copy_missing_verilog_files()

        # Step 2: Run synthesis on all circuits
        log_print("\n[Step 2] Running synthesis on all ISCAS85 circuits...")
        results = {}

        for circuit in ISCAS85_CIRCUITS:
            original, optimized, synth_time = run_synthesis(circuit)
            results[circuit] = {
                'original': original,
                'optimized': optimized,
                'synth_time': synth_time
            }
            # Log intermediate results
            time_str = f"{synth_time:.2f}s" if synth_time else "N/A"
            log_print(f"  {circuit}: original={original}, optimized={optimized}, time={time_str}")

        # Step 3: Print summary table
        log_print("\n" + "="*80)
        log_print("SYNTHESIS RESULTS SUMMARY")
        log_print("="*80)
        log_print(f"{'Circuit':<10} {'Original':<12} {'Optimized':<12} {'Reduction':<12} {'Time (s)':<12}")
        log_print("-"*80)

        total_original = 0
        total_optimized = 0
        total_time = 0.0

        for circuit in ISCAS85_CIRCUITS:
            orig = results[circuit]['original']
            opt = results[circuit]['optimized']
            synth_time = results[circuit]['synth_time']

            if orig is not None and opt is not None:
                reduction = ((orig - opt) / orig) * 100
                time_str = f"{synth_time:.2f}" if synth_time else "N/A"
                log_print(f"{circuit:<10} {orig:<12} {opt:<12} {reduction:>6.2f}%      {time_str:<12}")
                total_original += orig
                total_optimized += opt
                if synth_time:
                    total_time += synth_time
            else:
                log_print(f"{circuit:<10} {'FAILED':<12} {'FAILED':<12} {'N/A':<12} {'N/A':<12}")

        log_print("-"*80)
        if total_original > 0:
            total_reduction = ((total_original - total_optimized) / total_original) * 100
            log_print(f"{'TOTAL':<10} {total_original:<12} {total_optimized:<12} {total_reduction:>6.2f}%      {total_time:<.2f}")

        log_print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Save results to JSON
        json_file = os.path.join(AUTOHOG_DIR, 'iscas85_results.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        log_print(f"\nResults saved to:")
        log_print(f"  JSON: {json_file}")
        log_print(f"  Log:  {log_file}")


if __name__ == '__main__':
    main()
