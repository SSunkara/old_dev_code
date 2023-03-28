import gzip
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import traceback
from io import IOBase


class ActivityException(Exception):
    """
    Exception for Genome activities that holds an error message and a specific exit code
    """

    def __init__(self, message, exit_code=1):
        self.message = message
        self.exit_code = exit_code

    def print_traceback(self):
        console_print(traceback.format_exc())


def ensure_dir(file_path):
    if not os.path.exists(file_path):
        os.mkdir(file_path)


def error_and_out(message, exit_code=1):
    print(message)
    sys.exit(exit_code)


def console_print(message):
    print("\nPROFILER: " + str(message) + "\n")
    sys.stdout.flush()


def safe_filename(filename):
    return re.sub('[^A-Za-z0-9._-]', '_', filename)


def escape_path(path):
    return "".join(["\"", path, "\""])


def escape_command(command):
    if platform.system() == "Windows":
        if "&" in command:
            return command.replace("&", "^&")
        else:
            return command
    elif ";" in command:
        return command.replace(";", "\\;")
    else:
        return command


def run_cmd(cmd, outfile=subprocess.PIPE, error_file=subprocess.PIPE, print_cmd=True, escape_cmd=True):
    """

    Runs the passed shell command

    Python version 3.7: Added the `capture_output` parameter. Do not use for the moment because PYTHON3 environment is
    only python version 3.6. Instead use `outfile` for capturing output.

    :param cmd:
    :param outfile:
    :param error_file:
    :param print_cmd:
    :param escape_cmd:
    :return:
    """

    sys.stdout.flush()
    if escape_cmd:
        cmd = escape_command(cmd)

    if (outfile != sys.stdout) and (outfile != subprocess.PIPE) and (outfile is not None):
        assert isinstance(outfile, IOBase), 'outfile was not passed a file'
        assert outfile.mode in ['w', 'a', 'wb', 'ab'], 'outfile not writeable'
        assert not outfile.closed, 'outfile is closed'

    if (error_file != sys.stderr) and (error_file != subprocess.PIPE) and (error_file is not None):
        assert isinstance(error_file, IOBase), 'errfile was not passed a file'
        assert error_file.mode in ['w', 'a', 'wb', 'ab'], 'errfile not writeable'
        assert not error_file.closed, 'errfile is closed'

    if print_cmd:
        if "--" in cmd:
            print("\n\t--".join(cmd.split(" --")))
        elif "-" in cmd:
            print("\n\t-".join(cmd.split(" -")))
        else:
            print("\n\t".join(cmd.split(" ")))
        print('\n')
        sys.stdout.flush()

    try:
        out = subprocess.run(cmd, shell=True, stdout=outfile, stderr=error_file, check=True)
        if outfile == subprocess.PIPE:
            sys.stdout.write(out.stdout.decode("utf-8"))
            return out.stdout.decode("utf-8")
        else:
            return out.returncode
    except subprocess.CalledProcessError as e:
        error_message = "System call returned a non-zero exit status={0} for command '{1}'.".format(
            e.returncode, e.cmd)
        if outfile == subprocess.PIPE:
            error_message += "\nstdout: {0}".format(e.stdout.decode("utf-8"))
        if error_file == subprocess.PIPE:
            error_message += "\nstderr: {0}".format(e.stderr.decode("utf-8"))
        raise RuntimeError(error_message)


def gunzip(filename):
    """

    Gunzips the input file to the same directory

    :param filename: File to be gunzipped
    :return:  path to the gunzipped file
    """

    assert is_gzipfile(filename)

    if filename.endswith('.tar.gz'):
        tar = tarfile.open(filename, 'r:gz')
        tar.extractall()
        tar.close()
        return filename[:-7]
    elif filename.endswith('.tar'):
        tar = tarfile.open(filename, 'r:')
        tar.extractall()
        tar.close()
        return filename[:-4]
    elif filename.endswith('.gz'):
        with gzip.open(filename, 'rb') as f_in:
            with open(os.path.splitext(filename)[0], 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return f_out.name


def is_gzipfile(filename):
    """
    If you want to check whether a file is a valid Gzip file, you can open it and read one byte from it.
    If it succeeds, the file is quite probably a gzip file, with one caveat: an empty file also succeeds this test.

    This was taken from the stack overflow post
    https://stackoverflow.com/questions/37874936/how-to-check-empty-gzip-file-in-python

    :param str filename: A path to a file
    :return: True if the file appears to be gzipped else false
    :rtype: bool
    """
    assert os.path.exists(filename), 'Input {} does not '.format(filename) + \
                                     'point to a file.'

    # check if file is empty
    if os.stat(filename).st_size == 0:
        return False

    # check if file is compressed
    with gzip.open(filename, 'rb') as f:
        try:
            f.read(1)
            return True
        except:
            return False


def gzip_file(filename):
    """
    Gzip a file according to https://docs.python.org/3/library/gzip.html

    :param filename: file to be gzipped
    :return: gzipped filename
    """
    with open(filename, 'rb') as f_in:
        with gzip.open(filename + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return filename + ".gz"


def bgzip_file(filename):
    out_file = filename + ".gz"
    cmd = "bgzip -c " + escape_path(filename) + " > " + escape_path(out_file)
    exit_code = subprocess.call(cmd, shell=True)
    if exit_code != 0:
        error_and_out("Problem while bgzipping file {0}!".format(filename), exit_code)
    return out_file


def sort_alphanumerical(l):
    """
    Sorts the given iterable in alphanumerical order
    Adapted from https://arcpy.wordpress.com/2012/05/11/sorting-alphanumeric-strings-in-python/

    Args:
        l: iterable

    Returns: list sorted alpha numerically

    """

    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def write_to_file(text, file_path):
    f = open(file_path, "w")
    f.write(text + "\n")
    f.close()
