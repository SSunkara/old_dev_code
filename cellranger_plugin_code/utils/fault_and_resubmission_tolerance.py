import glob
import os
import shutil

failedTracksFolder = os.path.join(str(os.getenv("shared_folder")), "__failed_tracks__")

# Message Types
ERROR = "error"
WARNING = "warning"

MESSAGE_FILE = {
    ERROR: "error_message.txt",
    WARNING: "warning_message.txt"
}


##############################################################################
# Resubmission Tolerance
##############################################################################

def clean_up_and_ensure_folder(folder_path):
    clean_up_folder(folder_path)
    _create_folder_safe(folder_path)
    return folder_path


def clean_up_file(file_path):
    if os.path.exists(file_path):
        print("Resubmission of task - cleaning up the following file from previous run: " + str(file_path))
        os.remove(file_path)
    return file_path


def clean_up_folder(folder_path):
    if os.path.exists(folder_path):
        print("Resubmission of task - cleaning up content of the following folder from previous run: " + str(folder_path))
        shutil.rmtree(folder_path)
    return folder_path


def cleaned_shared_task_folder():
    task_index = os.getenv("task_index")
    print("Using shared folder for task " + str(task_index) + " containing track(s) "
          + str(os.getenv('track_indices')) + ".")
    shared_task_folder = get_shared_task_folder(task_index)
    clean_up_and_ensure_folder(shared_task_folder)
    return shared_task_folder


def get_shared_task_folder(task_index):
    return os.path.join(os.getenv("shared_folder"), '_task_outputs', str(task_index))


def get_shared_task_folders(paired: bool = False):
    # Only compatible with the Genome module for now.
    sample_count = int(os.getenv('total_samples_0'))
    if paired:
        task_count = sample_count / 2
    else:
        task_count = sample_count

    res = []
    for task_i in range(task_count):
        res.append(get_shared_task_folder(task_i))
    return res


##############################################################################
# Fault Tolerance
##############################################################################

def ensure_failure_flag_is_cleared():
    track_indices = os.getenv("track_indices").split(",")
    for track in track_indices:
        clean_up_folder(os.path.join(failedTracksFolder, track))


def list_track_indices_reported_as_failed():
    if os.path.exists(failedTracksFolder):
        return [int(s) for s in os.listdir(failedTracksFolder)]
    else:
        return []


def report_task_tracks_as_failed(message=None, message_type=ERROR):
    _create_folder_safe(failedTracksFolder)
    track_indices = os.getenv("track_indices").split(",")
    for track in track_indices:
        task_folder = os.path.join(failedTracksFolder, track)
        _create_folder_safe(task_folder)
        if message is not None:
            with open(os.path.join(task_folder, MESSAGE_FILE[message_type]), "w") as f:
                f.write(message)


def read_message(track_index, message_type=ERROR):
    if message_type not in MESSAGE_FILE.keys():
        print("Message type {0} does not exist. Use message_type=ERROR instead.".format(message_type))
        message_type = ERROR

    message = ""
    message_file_list = glob.glob(os.path.join(failedTracksFolder, str(track_index), MESSAGE_FILE[message_type]))
    if len(message_file_list) != 0:
        with open(message_file_list[0], 'r') as f:
            message = f.readlines()
    return message


def pluralize(count, entity):
    return "{}{}{}".format(count, entity, "s" if count > 1 else "")


##############################################################################
# Shared Util
##############################################################################

def _create_folder_safe(folder_path):
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path, exist_ok=True)
        except FileExistsError:
            pass
