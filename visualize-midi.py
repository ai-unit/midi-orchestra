import argparse
import os

import librosa.display
import matplotlib.pyplot as plt
import pretty_midi as midi

import common


# MIDI note range (y-axis)
START_PITCH = 0
END_PITCH = 127

# Size of the diagram
WIDTH = 17
HEIGHT = 12

# Analysis sample rate
RESOLUTION = 100


def generate_piano_roll(score, title, path, start_pitch, end_pitch,
                        width, height, fs):
    """Save a piano roll image."""

    plt.figure()
    plt.figure(figsize=(width, height))
    plt.title(title)

    librosa.display.specshow(score.get_piano_roll(fs)[start_pitch:end_pitch],
                             hop_length=1, sr=fs,
                             x_axis='time', y_axis='cqt_note',
                             fmin=midi.note_number_to_hz(start_pitch))

    plt.tight_layout()
    plt.savefig(path)


def main():
    """User interface."""

    parser = argparse.ArgumentParser(
        description='Helper script to visualize MIDI files as '
                    'piano rolls which are saved as .png.')
    parser.add_argument('files',
                        metavar='path',
                        nargs='+',
                        help='path of input files (.mid). '
                             'accepts * as wildcard')
    parser.add_argument('--target_folder',
                        metavar='path',
                        help='folder path where '
                             'generated images are stored',
                        default=common.DEFAULT_TARGET_FOLDER)
    parser.add_argument('--pitch_start',
                        metavar='0-127',
                        type=int,
                        help='midi note range start (y-axis)',
                        choices=range(0, 127),
                        default=START_PITCH)
    parser.add_argument('--pitch_end',
                        metavar='0-127',
                        type=int,
                        help='midi note range end (y-axis)',
                        choices=range(0, 127),
                        default=END_PITCH)
    parser.add_argument('--resolution',
                        metavar='1-1000',
                        type=int,
                        help='analysis resolution',
                        choices=range(1, 1000),
                        default=RESOLUTION)
    parser.add_argument('--width',
                        metavar='1-100',
                        type=int,
                        help='width of figure (inches)',
                        choices=range(1, 100),
                        default=WIDTH)
    parser.add_argument('--height',
                        metavar='1-100',
                        type=int,
                        help='height of figure (inches)',
                        choices=range(1, 100),
                        default=HEIGHT)

    args = parser.parse_args()

    file_paths = common.get_files(args.files)

    height = args.height
    pitch_end = args.pitch_end
    pitch_start = args.pitch_start
    resolution = args.resolution
    target_folder_path = args.target_folder
    width = args.width

    if pitch_end < pitch_start:
        common.print_error('Error: Pitch range is smaller than 0!')

    common.check_target_folder(target_folder_path)

    for file_path in file_paths:
        if common.is_invalid_file(file_path):
            continue

        # Read MIDi file and clean up
        score = midi.PrettyMIDI(file_path)
        score.remove_invalid_notes()
        print('➜ Loaded "{}".'.format(file_path))

        # Generate piano roll images
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        plot_file_path = common.make_file_path(file_path,
                                               target_folder_path,
                                               ext='png')

        generate_piano_roll(score, base_name, plot_file_path,
                            pitch_start, pitch_end,
                            width, height,
                            resolution)

        print('Generated plot at "{}".'.format(plot_file_path))

        # Free pyplot memory
        plt.close('all')

        print('')

    print('Done!')


if __name__ == '__main__':
    main()
