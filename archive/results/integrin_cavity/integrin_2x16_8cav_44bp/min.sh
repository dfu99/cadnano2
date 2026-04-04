#!/bin/bash
#SBATCH -J integrin_2x16_8cav_44bp_min
#SBATCH -A gts-yke8
#SBATCH --time=01:00:00
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda/12.1.1 gcc/12.3.0

srun /storage/home/hcoda1/6/dfu71/scratch/oxDNA/build/bin/oxDNA input_min
