import os
from pathlib import Path

import pandas as pd

import utils.fault_and_resubmission_tolerance as rt
from utils import utils as u


##############################################################################
# Environment Variables
##############################################################################

shared_folder = os.getenv('shared_folder')
files_per_sample = int(os.environ['NUMBER_FILES_PER_SAMPLE'])
sample_sheet = os.environ['SAMPLE_SHEET']


##############################################################################
# Prepare Input files
##############################################################################

fastq_folder = Path(shared_folder, 'fastq_input').as_posix()

rt.clean_up_and_ensure_folder(fastq_folder)


input_file_names = []

i = 0
while True:
    fq_path = os.getenv(f'input_0_{i}')
    if fq_path is None:
        break
    file_name = Path(fq_path).name
    input_file_names.append(file_name)
    if file_name.endswith('.fq.gz'):
        file_name = file_name[:-len('.fq.gz')] + '.fastq.gz'
    elif file_name.endswith('.fq'):
        file_name = file_name[:-len('.fq')] + '.fastq'
    os.symlink(os.path.realpath(fq_path), Path(fastq_folder, file_name))
    i += 1

input_file_names.sort()

u.console_print('Input files:\n' + "\n".join(input_file_names))

sample_sheet_df = pd.read_csv(sample_sheet, sep='\t')

if len(sample_sheet_df.index) * files_per_sample != i:
    u.error_and_out(f"Number of lines in selected sample sheet ({len(sample_sheet_df.index)}) does not match number "
                    f"of samples. Input Files: {i}. Files per Sample: {files_per_sample}.")
