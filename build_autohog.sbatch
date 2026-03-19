#!/bin/bash
#SBATCH --job-name=build_autohog
#SBATCH --partition=eb
#SBATCH --time=01:00:00
#SBATCH --rsc p=1:t=32:c=32:m=64G
#SBATCH --output=build_autohog_%j.out
#SBATCH --error=build_autohog_%j.err

# Build AutoHog Apptainer container on SLURM cluster

echo "Job started on $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"

cd $SLURM_SUBMIT_DIR

# Detect container runtime
if command -v apptainer &> /dev/null; then
    BUILD_CMD="apptainer build"
    echo "Using Apptainer"
elif command -v singularity &> /dev/null; then
    BUILD_CMD="singularity build"
    echo "Using Singularity"
else
    echo "Error: Neither Apptainer nor Singularity found!"
    exit 1
fi

echo "Building autohog container..."

if $BUILD_CMD --help | grep -q fakeroot; then
    echo "Building with fakeroot..."
    $BUILD_CMD --fakeroot autohog.sif autohog.def
else
    echo "Building without fakeroot..."
    $BUILD_CMD autohog.sif autohog.def
fi

if [ $? -eq 0 ]; then
    echo "Container built successfully!"
    ls -lh autohog.sif
else
    echo "Container build failed!"
    exit 1
fi

echo "Job completed on $(date)"
