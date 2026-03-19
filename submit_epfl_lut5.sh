#!/bin/bash
# Submit EPFL benchmark synthesis jobs with LUT5 configuration to SLURM.
# LUT5 config: searchnum_up=5, searchnum_low=5, replace_num=3

# Ensure autohog.sif container exists
if [ ! -f "autohog.sif" ]; then
    echo "ERROR: autohog.sif not found. Build it first with:"
    echo "  sbatch build_autohog.sbatch"
    exit 1
fi

mkdir -p logs

# LUT5 parameters
SEARCHNUM_UP=5
SEARCHNUM_LOW=5
REPLACE_NUM=3

# Circuit-specific resource configurations
# Format: circuit:partition:time:rsc
# Small circuits: 32 threads, 96GB
# Medium circuits: 56 threads, 256GB
# Large circuits: 112 threads, 512GB
CONFIGS="
ctrl:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
dec:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
i2c:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
int2float:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
cavlc:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
priority:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
router:gr20100b:06:00:00:p=1:t=32:c=32:m=96G
arbiter:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
voter:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
mem_ctrl:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
adder:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
bar:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
max:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
sin:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
sqrt:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
square:gr20100b:06:00:00:p=1:t=56:c=56:m=256000
log2:gr20100b:06:00:00:p=1:t=112:c=112:m=512000
hyp:gr20100b:06:00:00:p=1:t=112:c=112:m=512000
div:gr20100b:06:00:00:p=1:t=112:c=112:m=512000
multiplier:gr20100b:06:00:00:p=1:t=112:c=112:m=512000
"

SUBMITTED=0

echo "Submitting EPFL benchmark synthesis jobs (LUT5 config)"
echo "  searchnum_up=$SEARCHNUM_UP, searchnum_low=$SEARCHNUM_LOW, replace_num=$REPLACE_NUM"
echo "========================================================"

for config in $CONFIGS; do
    circuit=$(echo "$config" | cut -d: -f1)
    partition=$(echo "$config" | cut -d: -f2)
    time_limit=$(echo "$config" | cut -d: -f3-5)
    rsc=$(echo "$config" | cut -d: -f6-9)

    JOB_NAME="${circuit}_lut5"

    sbatch --job-name="$JOB_NAME" \
           --partition="$partition" \
           --time="$time_limit" \
           --rsc "$rsc" \
           run_epfl_synth.sbatch "$circuit" "$SEARCHNUM_UP" "$SEARCHNUM_LOW" "$REPLACE_NUM"

    SUBMITTED=$((SUBMITTED + 1))
done

echo ""
echo "========================================================"
echo "Submitted $SUBMITTED jobs"
echo "Use 'squeue -u \$USER' to monitor job status"
echo "Logs will be saved to logs/ directory"
echo ""
echo "After jobs complete, check runtimes with:"
echo "  grep 'Total runtime' logs/epfl_*_lut5_*.out"
echo "  grep 'Optimized gate num' logs/epfl_*_lut5_*.out"
