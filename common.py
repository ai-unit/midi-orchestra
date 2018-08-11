import argparse
import sys


DEFAULT_TARGET_FOLDER = './generated/'


def print_error(*args):
    """Prints an error message and closes the script."""

    print(*args, file=sys.stderr)
    sys.exit(1)


def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]" % (x,))
    return x
