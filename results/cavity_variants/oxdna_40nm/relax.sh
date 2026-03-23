#!/bin/bash
#SBATCH -J cav40nm_relax
#SBATCH -A gts-yke8
#SBATCH -N1 --gres=gpu:RTX_6000:1
#SBATCH --time=10:00:00
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda/12.1.1 gcc/12.3.0

srun /storage/home/hcoda1/6/dfu71/scratch/oxDNA/build/bin/oxDNA input_relax
