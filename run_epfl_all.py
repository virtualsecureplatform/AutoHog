#!/usr/bin/env python3
"""
Run AutoHog synthesis on all EPFL benchmark circuits with LUT5 configuration
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

# EPFL benchmark circuits
ARITHMETIC_CIRCUITS = [
    'adder', 'bar', 'div', 'hyp', 'log2',
    'max', 'multiplier', 'sin', 'sqrt', 'square'
]
RANDOM_CONTROL_CIRCUITS = [
    'arbiter', 'cavlc', 'ctrl', 'dec', 'i2c',
    'int2float', 'mem_ctrl', 'priority', 'router', 'voter'
]
ALL_CIRCUITS = ARITHMETIC_CIRCUITS + RANDOM_CONTROL_CIRCUITS

CIRCUIT_CATEGORY = {}
for c in ARITHMETIC_CIRCUITS:
    CIRCUIT_CATEGORY[c] = 'arithmetic'
for c in RANDOM_CONTROL_CIRCUITS:
    CIRCUIT_CATEGORY[c] = 'random_control'

AUTOHOG_DIR = os.path.dirname(os.path.abspath(__file__))
VERILOG_DIR = os.path.join(AUTOHOG_DIR, 'Verilog_file')
EPFL_SUBMODULE_DIR = os.path.join(VERILOG_DIR, 'epfl')
EXACT_SYNTH_EPFL_DIR = os.path.join(AUTOHOG_DIR, '..', 'ExactTFHEsynth', 'test', 'epfl', 'benchmarks')


def copy_epfl_verilog_files():
    """Copy EPFL verilog files to Verilog_file/ directory."""
    copied = []
    for circuit in ALL_CIRCUITS:
        dest_file = os.path.join(VERILOG_DIR, f'{circuit}.v')
        if os.path.exists(dest_file):
            continue

        category = CIRCUIT_CATEGORY[circuit]
        # Try ExactTFHESynth benchmarks first
        src = os.path.join(EXACT_SYNTH_EPFL_DIR, category, f'{circuit}.v')
        if not os.path.exists(src):
            # Try git submodule
            src = os.path.join(EPFL_SUBMODULE_DIR, category, f'{circuit}.v')

        if os.path.exists(src):
            shutil.copy(src, dest_file)
            copied.append(circuit)
            print(f"Copied: {circuit}.v")
        else:
            print(f"Warning: Could not find {circuit}.v")
    return copied


def run_synthesis(circuit_name, searchnum_up=5, searchnum_low=5, replace_num=3):
    """Run synthesis on a single EPFL circuit. Returns (original, optimized, time) or Nones."""
    print(f"\n{'='*60}")
    print(f"Processing: {circuit_name}")
    print(f"Config: searchnum_up={searchnum_up}, searchnum_low={searchnum_low}, replace_num={replace_num}")
    print('='*60)

    verilog_file = os.path.join(VERILOG_DIR, f'{circuit_name}.v')
    if not os.path.exists(verilog_file):
        print(f"Error: {verilog_file} not found")
        return None, None, None

    start_time = time.time()

    # Generate yosys build script
    template_file = os.path.join(AUTOHOG_DIR, 'build_template.ys')
    output_file = os.path.join(AUTOHOG_DIR, 'build.ys')

    with open(template_file, 'r') as f:
        template = f.read()

    ys_content = template.replace("{filename}", f"Verilog_file/{circuit_name}")
    with open(output_file, 'w') as f:
        f.write(ys_content)

    # Run yosys
    print("Running Yosys...")
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

    # Run optimization
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

    elapsed_time = time.time() - start_time

    original_match = re.search(r'Original gate num:\s*(\d+)', output)
    optimized_match = re.search(r'Optimized gate num:\s*(\d+)', output)

    original_count = int(original_match.group(1)) if original_match else None
    optimized_count = int(optimized_match.group(1)) if optimized_match else None

    print(f"Synthesis time: {elapsed_time:.2f}s")

    return original_count, optimized_count, elapsed_time


def main():
    # Parse optional LUT config from command line
    searchnum_up = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    searchnum_low = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    replace_num = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(AUTOHOG_DIR, f'epfl_synthesis_{timestamp}.log')

    with open(log_file, 'w') as log:
        def log_print(msg=""):
            print(msg)
            log.write(msg + "\n")
            log.flush()

        log_print("="*60)
        log_print("AutoHog EPFL Benchmark Synthesis (LUT5)")
        log_print(f"Config: searchnum_up={searchnum_up}, searchnum_low={searchnum_low}, replace_num={replace_num}")
        log_print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_print("="*60)

        # Copy missing verilog files
        log_print("\n[Step 1] Checking EPFL verilog files...")
        copy_epfl_verilog_files()

        # Run synthesis
        log_print("\n[Step 2] Running synthesis on all EPFL circuits...")
        results = {}

        for circuit in ALL_CIRCUITS:
            original, optimized, synth_time = run_synthesis(
                circuit, searchnum_up, searchnum_low, replace_num
            )
            results[circuit] = {
                'original': original,
                'optimized': optimized,
                'synth_time': synth_time,
                'category': CIRCUIT_CATEGORY[circuit]
            }
            time_str = f"{synth_time:.2f}s" if synth_time else "N/A"
            log_print(f"  {circuit}: original={original}, optimized={optimized}, time={time_str}")

        # Summary table
        log_print("\n" + "="*80)
        log_print("EPFL SYNTHESIS RESULTS SUMMARY")
        log_print(f"Config: searchnum_up={searchnum_up}, searchnum_low={searchnum_low}, replace_num={replace_num}")
        log_print("="*80)
        log_print(f"{'Circuit':<15} {'Category':<15} {'Original':<12} {'Optimized':<12} {'Reduction':<12} {'Time (s)':<12}")
        log_print("-"*80)

        total_original = 0
        total_optimized = 0
        total_time = 0.0

        for circuit in ALL_CIRCUITS:
            orig = results[circuit]['original']
            opt = results[circuit]['optimized']
            synth_time = results[circuit]['synth_time']
            category = results[circuit]['category']

            if orig is not None and opt is not None:
                reduction = ((orig - opt) / orig) * 100
                time_str = f"{synth_time:.2f}" if synth_time else "N/A"
                log_print(f"{circuit:<15} {category:<15} {orig:<12} {opt:<12} {reduction:>6.2f}%      {time_str:<12}")
                total_original += orig
                total_optimized += opt
                if synth_time:
                    total_time += synth_time
            else:
                log_print(f"{circuit:<15} {category:<15} {'FAILED':<12} {'FAILED':<12} {'N/A':<12} {'N/A':<12}")

        log_print("-"*80)
        if total_original > 0:
            total_reduction = ((total_original - total_optimized) / total_original) * 100
            log_print(f"{'TOTAL':<15} {'':<15} {total_original:<12} {total_optimized:<12} {total_reduction:>6.2f}%      {total_time:<.2f}")

        log_print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        json_file = os.path.join(AUTOHOG_DIR, 'epfl_results.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        log_print(f"\nResults saved to:")
        log_print(f"  JSON: {json_file}")
        log_print(f"  Log:  {log_file}")


if __name__ == '__main__':
    main()
