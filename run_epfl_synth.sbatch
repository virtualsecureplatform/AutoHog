#!/bin/bash
#SBATCH --job-name=epfl_synth
#SBATCH --partition=gr20100b
#SBATCH --time=06:00:00
#SBATCH --rsc p=1:t=32:c=32:m=96G
#SBATCH --output=logs/epfl_%x_%j.out
#SBATCH --error=logs/epfl_%x_%j.err

# Usage: sbatch [resource options] run_epfl_synth.sbatch <circuit> <searchnum_up> <searchnum_low> <replace_num>
# Example: sbatch --job-name=adder_lut5 run_epfl_synth.sbatch adder 5 5 3

CIRCUIT=$1
SEARCHNUM_UP=${2:-5}
SEARCHNUM_LOW=${3:-5}
REPLACE_NUM=${4:-3}

if [ -z "$CIRCUIT" ]; then
    echo "Usage: sbatch [resource options] run_epfl_synth.sbatch <circuit> [searchnum_up] [searchnum_low] [replace_num]"
    exit 1
fi

# Circuit name -> category mapping
declare -A CIRCUIT_CATEGORY
for name in adder bar div hyp log2 max multiplier sin sqrt square; do
    CIRCUIT_CATEGORY[$name]="arithmetic"
done
for name in arbiter cavlc ctrl dec i2c int2float mem_ctrl priority router voter; do
    CIRCUIT_CATEGORY[$name]="random_control"
done

CATEGORY="${CIRCUIT_CATEGORY[$CIRCUIT]}"
if [ -z "$CATEGORY" ]; then
    echo "ERROR: Unknown EPFL circuit '$CIRCUIT'"
    exit 1
fi

START_TIME=$(date +%s)

echo "Job started on $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "Circuit: $CIRCUIT ($CATEGORY)"
echo "Config: searchnum_up=$SEARCHNUM_UP, searchnum_low=$SEARCHNUM_LOW, replace_num=$REPLACE_NUM"

cd $SLURM_SUBMIT_DIR
AUTOHOG_DIR=$(pwd)

mkdir -p logs

# Ensure EPFL verilog file is available
VERILOG_DEST="Verilog_file/${CIRCUIT}.v"
if [ ! -f "$VERILOG_DEST" ]; then
    # Try to copy from ExactTFHESynth benchmark
    EPFL_SRC="$HOME/ExactTFHEsynth/test/epfl/benchmarks/${CATEGORY}/${CIRCUIT}.v"
    if [ -f "$EPFL_SRC" ]; then
        cp "$EPFL_SRC" "$VERILOG_DEST"
        echo "Copied ${CIRCUIT}.v from ExactTFHEsynth benchmarks"
    # Try git submodule
    elif [ -f "Verilog_file/epfl/${CATEGORY}/${CIRCUIT}.v" ]; then
        cp "Verilog_file/epfl/${CATEGORY}/${CIRCUIT}.v" "$VERILOG_DEST"
        echo "Copied ${CIRCUIT}.v from EPFL submodule"
    else
        echo "ERROR: Cannot find ${CIRCUIT}.v"
        exit 1
    fi
fi

# Generate yosys build script from template
TEMPLATE_FILE="build_template.ys"
BUILD_FILE="build_${CIRCUIT}.ys"
sed "s|{filename}|Verilog_file/${CIRCUIT}|g" "$TEMPLATE_FILE" > "$BUILD_FILE"

# Run yosys synthesis inside container
echo "Running Yosys synthesis for ${CIRCUIT}..."
apptainer exec --bind ${AUTOHOG_DIR}:/AutoHog ${AUTOHOG_DIR}/autohog.sif \
    yosys /AutoHog/${BUILD_FILE}

if [ $? -ne 0 ]; then
    echo "Yosys synthesis failed for ${CIRCUIT}!"
    rm -f "$BUILD_FILE"
    exit 1
fi

# Run AutoHog search_replace optimization
echo "Running AutoHog optimization (searchnum_up=$SEARCHNUM_UP, searchnum_low=$SEARCHNUM_LOW, replace_num=$REPLACE_NUM)..."
apptainer exec --bind ${AUTOHOG_DIR}:/AutoHog ${AUTOHOG_DIR}/autohog.sif \
    python3 /AutoHog/search_replace.py "$CIRCUIT" "$SEARCHNUM_UP" "$SEARCHNUM_LOW" "$REPLACE_NUM"

if [ $? -ne 0 ]; then
    echo "Optimization failed for ${CIRCUIT}!"
    rm -f "$BUILD_FILE"
    exit 1
fi

# Convert DAG to JSON
echo "Converting DAG to JSON..."
apptainer exec --bind ${AUTOHOG_DIR}:/AutoHog ${AUTOHOG_DIR}/autohog.sif \
    python3 /AutoHog/dag2json.py "$CIRCUIT"

# Cleanup temporary build script
rm -f "$BUILD_FILE"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECS=$((ELAPSED % 60))

echo ""
echo "Circuit: $CIRCUIT"
echo "Config: LUT inputs max=$SEARCHNUM_UP, min=$SEARCHNUM_LOW, replace_min=$REPLACE_NUM"
printf "Total runtime: %02d:%02d:%02d (HH:MM:SS)\n" $HOURS $MINUTES $SECS
echo "Total runtime: ${ELAPSED} seconds"
echo "Job completed on $(date)"
