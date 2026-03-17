#!/bin/bash
#SBATCH -J oxDNA_origami_min
#SBATCH -A gts-yke8
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda

srun /storage/coda1/p-yke8/0/shared/oxDNA/build/bin/oxDNA input_min
