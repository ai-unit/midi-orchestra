import argparse
import glob
import os
import sys


DEFAULT_TARGET_FOLDER = './generated/'


def print_error(*args):
    """Prints an error message and closes the script."""

    print(*args, file=sys.stderr)
    sys.exit(1)


def restricted_float(x):
    """Checks if user argument is a float in range 0.0-1.0."""

    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]" % (x,))
    return x


def get_files(files):
    """Accepts multiple files in an array or glob pattern string."""

    file_paths = glob.glob(files[0]) if len(files) == 1 else files

    if len(file_paths) == 0:
        print_error('Error: could not find any files with this pattern.')

    return file_paths


def make_file_path(file_path, target_folder_path, ext='mid', suffix=None):
    """Generates a file path for storing new files."""

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    file_name = '{}{}.{}'.format(base_name,
                                 '-{}'.format(suffix) if suffix else '',
                                 ext)
    return os.path.join(target_folder_path, file_name)


def check_target_folder(target_folder_path):
    """Create target folder when it does not exist."""

    if not os.path.isdir(target_folder_path):
        print('Create target folder at "{}".'.format(target_folder_path))
        os.makedirs(target_folder_path)


def is_invalid_file(file_path):
    """Check if file is a valid MIDI document."""

    if not os.path.isfile(file_path):
        print('Warning: "{}" could not be found or is a folder '
              'Ignore it!\n'.format(file_path))
        return True

    if not file_path.endswith('.mid'):
        print('Warning: File "{}" does not end with ".mid". '
              'Ignore it!\n'.format(file_path))
        return True
    return False
