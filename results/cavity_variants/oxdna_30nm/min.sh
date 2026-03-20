#!/bin/bash
#SBATCH -J cavity30nm_min
#SBATCH -A gts-yke8
#SBATCH --time=01:00:00
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda

srun /storage/coda1/p-yke8/0/shared/oxDNA/build/bin/oxDNA input_min
