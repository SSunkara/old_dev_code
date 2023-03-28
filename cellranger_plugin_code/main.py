import os
import shutil
from pathlib import Path

import pandas as pd
import numpy as np

import utils.fault_and_resubmission_tolerance as rt
from utils import utils as u

import subprocess
import re

##############################################################################
# Environment Variables
##############################################################################

max_threads = os.environ['max_threads']
max_memory = os.environ['max_memory']

sample_sheet = os.environ['SAMPLE_SHEET']

sample_id_column = os.environ['SAMPLE_ID_COLUMN']

# GEX
use_gex_library = os.environ['GENE_EXPRESSION_LIBRARY'] == 'true'
gex_id_column = os.getenv('GEX_ID_COLUMN')
gex_reference = os.getenv('GEX_REFERENCE')
include_introns = os.getenv('INCLUDE_INTRONS')
no_bam = os.getenv('NO_BAM')
gex_cmo_set = os.getenv('CMO_SET')
cell_count_column = os.getenv('CELL_COUNT_COLUMN')

# VDJ
use_vdj_library = os.environ['VDJ_LIBRARY'] == 'true'
vdj_id_column = os.getenv('VDJ_ID_COLUMN')
vdj_reference = os.getenv('VDJ_REFERENCE')
vdj_type = os.getenv('VDJ_LIBRARY_TYPE')

# Multiplexing Capture
use_multiplexing_capture_library = os.environ['MULTIPLEXING_CAPTURE_LIBRARY'] == 'true'
multiplexing_id_column = os.getenv('MULTIPLEXING_ID_COLUMN')
hashing_tag_column = os.getenv('HASHING_TAG_COLUMN')

# Antibody Capture
use_antibody_capture_library = os.environ['ANTIBODY_CAPTURE_LIBRARY'] == 'true'
antibody_capture_id_column = os.getenv('ANTIBODY_CAPTURE_ID_COLUMN')
feature_reference = os.getenv('FEATURE_REFERENCE')

# External tools packaged with CellRanger
bam2fastq_exec = os.getenv("bamtofastq_exec")
samtools = os.getenv("samtools")

##############################################################################
# Input files
##############################################################################

shared_folder = os.getenv('shared_folder')
fastq_folder = Path(shared_folder, 'fastq_input').absolute().as_posix()


##############################################################################
# Outputs
##############################################################################

task_output_folder = rt.cleaned_shared_task_folder()


##############################################################################
# Run once per row in sample sheet
##############################################################################

sample_sheet_df = pd.read_csv(sample_sheet, sep='\t')


def get_sample_sheet_value(r, column):
    if column not in r:
        raise Exception(f"Column '{str(column)}' not present in selected "
                        f"sample sheet file with columns {str(list(r.keys()))}.")
    return r[column]


task_index = int(os.getenv("task_index"))
row = sample_sheet_df.iloc[task_index]


##############################################################################
# Prepare cellranger multi config file
##############################################################################

print("\n##############################################################################\n"
      f"# Sample {task_index + 1}:\n{str(row.to_dict())}\n"
      "##############################################################################\n")

sample_name = get_sample_sheet_value(row, sample_id_column)
config_file = sample_name + '_gex_cellmux_config.csv'

HT_id = get_sample_sheet_value(row, hashing_tag_column)
HT_list = HT_id.split(',')

cell_count = get_sample_sheet_value(row, cell_count_column)

with open(config_file, 'wt') as file:
    file.write("[libraries]\n")
    file.write("fastq_id,fastqs,feature_types\n")
    if use_gex_library:
        gex_fastq_id = get_sample_sheet_value(row, gex_id_column)
        file.write(f"{gex_fastq_id},{fastq_folder},Gene Expression\n")
    if use_vdj_library:
        pass
    if use_multiplexing_capture_library:
        multiplexing_capture_id = get_sample_sheet_value(row, multiplexing_id_column)
        file.write(f"{multiplexing_capture_id},{fastq_folder},Multiplexing Capture\n")
    if use_antibody_capture_library:
        pass
    file.write('\n')

    if use_gex_library:
        file.write(f'[gene-expression]\n')
        file.write(f'reference,{gex_reference}\n')
        file.write(f'include-introns,{include_introns}\n')
        file.write(f'no-bam,{no_bam}\n')
        if gex_cmo_set != '':
            file.write(f'cmo-set,{Path(gex_cmo_set).absolute().as_posix()}\n')
        file.write('\n')

    if use_vdj_library:
        pass
    if use_multiplexing_capture_library:
        file.write('[samples]\n')
        file.write('sample_id,cmo_ids\n')
        for HT in HT_list:
            file.write(f'{HT},{HT}\n')
        file.write('\n')
    if use_antibody_capture_library:
        pass

u.run_cmd(f"cat {config_file}", outfile=None, error_file=None)

##############################################################################
# Run Cell Ranger multi
##############################################################################

cellranger_exec = os.path.join(os.getenv("CELLRANGER_DIR"), "cellranger")

cellranger_memory = int(int(max_memory) / 1024 - 1)

cmd = f'"{cellranger_exec}" multi' \
      f' --id={sample_name}' \
      f' --csv={config_file}' \
      f' --disable-ui' \
      f' --localcores {int(max_threads)}' \
      f' --localmem {cellranger_memory}' \
      f' --localvmem {cellranger_memory}'

if os.getenv('CELLRANGER_DRY_RUN') == 'true':
    cmd += ' --dry'

u.console_print('Running Cell Ranger multi.')
u.run_cmd(cmd, outfile=None, error_file=None)

##############################################################################
# Run BamToFastq
##############################################################################

bamfq_path = Path(sample_name + '_BAM2FQ')
dest_folder = os.path.basename(bamfq_path)
demux_folder = sample_name + '_DEMUX'
readsperfq = 75000000
    
if not os.path.isdir(bamfq_path):
    os.mkdir(bamfq_path)

u.console_print(f"bamfq_path: {bamfq_path}")

for HT in HT_list:

    HT = str(HT)
    bam = Path(sample_name, "outs", "per_sample_outs", HT, "count", "sample_alignments.bam").absolute().as_posix()
    metrics = Path(sample_name, "outs", "per_sample_outs", HT, "metrics_summary.csv").absolute().as_posix()

    HT_path = Path(bamfq_path, HT).as_posix()
    rt.clean_up_folder(HT_path)

    bam2fq_cmd = f'{bam2fastq_exec}' \
                 f' --traceback' \
                 f' --nthreads={max_threads}' \
                 f' --reads-per-fastq={readsperfq}' \
                 f' {bam}' \
                 f' {bamfq_path}/{HT}'

    u.console_print(f"Running bamtofastq on {bam} file.")
    u.run_cmd(bam2fq_cmd, outfile=None, error_file=None)

    ##################################################################################
    # Re-Run cellranger multi for multiomics analysis - GEX, VDJ and Antibody Capture
    # Code needs to be refactored. This is just a quick and dirty implementation here.
    # Include error checking code in the refactored version.
    ##################################################################################
    gex_cmd = f'{samtools}' \
              f' view -H {bam}' \
              f' | grep "Gene Expression"'

    libinfo = subprocess.getoutput(gex_cmd)
    m = re.search('"library_id":\d+', libinfo)
    myval = int(m.group(0).split(":")[1])
    
    #################################################################################
    # Find the corresponding GEX library files in the bamfq_path
    #################################################################################
    RGcmd =  f'ls -d {HT_path}/{sample_name}_{myval}_*'
    gexfolder = subprocess.getoutput(RGcmd)
    gexfolder = os.path.abspath(gexfolder)

    ################################################################################
    # Extract number of cells assigned to the sample
    ################################################################################
    cellscmd = f"grep 'Cells assigned to this sample'" \
               f" {metrics}"
    
    cellsstr = subprocess.getoutput(cellscmd)
    
    c = re.search('Cells assigned to this sample,"\d+,?\d+\s', cellsstr)
    
    force_cells = c.group(0).split("\"")[1]
    force_cells = int(force_cells.replace(',',''))

    ################################################################################
    # Generate the config file required by the Cell Ranger multiomics pipeline.
    ################################################################################

    multiomics_config_file = sample_name + '_vdj_fb_config.csv'

    with open(multiomics_config_file, 'wt') as file:

        file.write("[libraries]\n")
        file.write("fastq_id,fastqs,feature_types\n")
        file.write(f"bamtofastq,{gexfolder},Gene Expression\n")

        vdj_fastq_id = get_sample_sheet_value(row, vdj_id_column)
        file.write(f"{vdj_fastq_id},{fastq_folder},{vdj_type}\n")

        antibody_capture_id = get_sample_sheet_value(row, antibody_capture_id_column)
        file.write(f"{antibody_capture_id},{fastq_folder},Antibody Capture\n")
        file.write('\n')

        file.write(f'[gene-expression]\n')
        file.write(f'reference,{gex_reference}\n')
     
        if np.isnan(np.float64(row['Cell Count'])):
            file.write(f'force-cells,{force_cells}\n')
        else:
            file.write(f'force-cells,{int(cell_count)}\n')
        file.write(f'check-library-compatibility,false\n')
        file.write('\n')

        file.write('[vdj]\n')
        file.write(f'reference,{vdj_reference}\n')
        file.write('\n')

        file.write('[feature]\n')
        file.write(f'reference,{feature_reference}\n')
        file.write('\n')

    u.run_cmd(f"cat {multiomics_config_file}", outfile=None, error_file=None)

    ###################################################################################
    ###################################################################################
    # Run Cell Ranger multi for multiomics datasets
    # Not parallelized at this time, but consider a subprocess here for parallelization
    ###################################################################################

    cmd = f'"{cellranger_exec}" multi' \
          f' --id={sample_name}_{HT}' \
          f' --csv={multiomics_config_file}' \
          f' --disable-ui' \
          f' --localcores {int(max_threads)}' \
          f' --localmem {cellranger_memory}' \
          f' --localvmem {cellranger_memory}'

    if os.getenv('CELLRANGER_DRY_RUN') == 'true':
        cmd += ' --dry'

    u.console_print('Running Cell Ranger multi for multiomics datasets.')
    u.run_cmd(cmd, outfile=None, error_file=None)

    finaldir = sample_name + '_' + HT
    mri_find = f'ls {finaldir}/*mri.tgz'
    mri_file = subprocess.getoutput(mri_find)

    shutil.move(Path(finaldir, 'outs').as_posix(), Path(task_output_folder, finaldir).as_posix())
    shutil.move(Path(mri_file), Path(task_output_folder, finaldir).as_posix())
    
##############################################################################
# Create Output Files
##############################################################################

shutil.move(Path(sample_name, 'outs').as_posix(), Path(task_output_folder, demux_folder).as_posix())
shutil.move(Path(bamfq_path), Path(task_output_folder, dest_folder).as_posix())

