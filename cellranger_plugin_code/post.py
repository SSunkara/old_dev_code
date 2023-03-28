import os
import shutil
from pathlib import Path

import utils.fault_and_resubmission_tolerance as rt
from utils import utils as u

generic_output_layer = os.getenv('output_generic_data_0')


##############################################################################
# Export Results
##############################################################################

export_results = os.environ['POST_COMMAND_EXPORT_RESULTS'] == "true"
export_folder = os.getenv('POST_COMMAND_EXPORT_FOLDER')

u.console_print("Exporting Results to Data Lake")
index: int = 0
while True:
    task_output_folder = rt.get_shared_task_folder(index)
    if not os.path.isdir(task_output_folder):
        break
    if export_results:
        export_ignore = None
        if os.environ['POST_COMMAND_EXPORT_EXCLUDE_BAM'] == "true":
            export_ignore = shutil.ignore_patterns('*.bam', '*.bam.bai')
        shutil.copytree(task_output_folder, export_folder, dirs_exist_ok=True, ignore=export_ignore)
    if generic_output_layer is not None:
        for e in os.listdir(task_output_folder):
            shutil.move(Path(task_output_folder, e), Path(generic_output_layer, 'cellranger_multi', e))
    index += 1
