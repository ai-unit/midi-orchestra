import argparse
import glob
import math
import os

import pretty_midi as midi

import common


DEFAULT_DURATION = 60


def find_elements_in_range(elements, start_time, end_time):
    """Filters elements which are within a time range."""

    filtered_elements = []

    for item in elements:
        if hasattr(item, 'start') and hasattr(item, 'end'):
            start = item.start
            end = item.end
        elif hasattr(item, 'time'):
            start = item.time
            end = item.time

        if not (end <= start_time or start >= end_time):
            if hasattr(item, 'start') and hasattr(item, 'end'):
                item.start = item.start - start_time
                item.end = item.end - start_time
            elif hasattr(item, 'time'):
                item.time = item.time - start_time

            filtered_elements.append(item)

    return filtered_elements


def split_score(score, split_every_sec):
    """Break the MIDI file into smaller parts."""

    end_time = score.get_end_time()

    # Get instruments
    instruments = score.instruments

    # Get all time signature changes
    time_signature_changes = score.time_signature_changes

    # Get all key changes
    key_changes = score.key_signature_changes

    print('Score with {} instruments, '
          '{} signature changes, '
          '{} key changes and duration of {} sec.'.format(
              len(instruments),
              len(time_signature_changes),
              len(key_changes),
              end_time))

    last_time_signature_change = None
    if len(time_signature_changes) > 0:
        last_time_signature_change = time_signature_changes[0]

    last_key_change = None
    if len(key_changes) > 0:
        last_key_change = key_changes[0]

    splits = []

    # Split score into smaller time spans
    for split_index, split_start_time in enumerate(range(0,
                                                         math.ceil(end_time),
                                                         split_every_sec)):
        split_end_time = min(split_start_time + split_every_sec, end_time)

        split_instruments = []
        split_notes_counter = 0

        print('Generate split #{} from {} sec - {} sec.'.format(
            split_index + 1, split_start_time, split_end_time))

        for instrument in instruments:
            # Find notes for this instrument in this range
            split_notes = find_elements_in_range(instrument.notes,
                                                 split_start_time,
                                                 split_end_time)

            split_notes_counter += len(split_notes)

            # Create new instrument
            split_instrument = midi.Instrument(program=instrument.program,
                                               name=instrument.name)

            split_instrument.notes = split_notes
            split_instruments.append(split_instrument)

        # Find key and time signature changes
        split_time_changes = find_elements_in_range(time_signature_changes,
                                                    split_start_time,
                                                    split_end_time)

        if len(split_time_changes) > 0:
            last_time_signature_change = split_time_changes[-1]
        elif last_time_signature_change:
            split_time_changes = [last_time_signature_change]

        split_key_signature_changes = find_elements_in_range(key_changes,
                                                             split_start_time,
                                                             split_end_time)

        if len(split_key_signature_changes) > 0:
            last_key_change = split_key_signature_changes[-1]
        elif last_key_change:
            split_key_signature_changes = [last_key_change]

        print('Found {} notes, '
              'added {} key changes and '
              '{} time signature changes.'.format(
                  split_notes_counter,
                  len(split_key_signature_changes),
                  len(split_time_changes)))

        splits.append({'instruments': split_instruments,
                       'time_signature_changes': split_time_changes,
                       'key_signature_changes': split_key_signature_changes})

    return splits


def generate_files(base_name, target_folder, splits):
    """Saves multiple splitted MIDI files in a folder."""

    for split_index, split in enumerate(splits):
        split_score = midi.PrettyMIDI()
        split_score.time_signature_changes = split['time_signature_changes']
        split_score.key_signature_changes = split['key_signature_changes']
        split_score.instruments = split['instruments']

        # Save MIDI file
        split_file_name = '{}-split-{}.mid'.format(base_name, split_index + 1)
        split_file_path = os.path.join(target_folder, split_file_name)
        split_score.write(split_file_path)

        print('Saved MIDI file at "{}".'.format(split_file_path))


def main():
    """User interface."""

    parser = argparse.ArgumentParser(
        description='Helper script to split MIDI files into '
                    'shorter sequences by a fixed duration.')
    parser.add_argument('files',
                        metavar='path',
                        nargs='+',
                        help='path of input files (.mid). '
                             'accepts * as wildcard')
    parser.add_argument('--target_folder',
                        metavar='path',
                        help='folder path where '
                             'generated results are stored',
                        default=common.DEFAULT_TARGET_FOLDER)
    parser.add_argument('--duration',
                        metavar='seconds',
                        type=int,
                        help='duration of every slice in seconds',
                        choices=range(1, 60 * 60),
                        default=DEFAULT_DURATION)

    args = parser.parse_args()

    file_paths = (
        glob.glob(args.files) if isinstance(args.files, str) else args.files)
    target_folder_path = args.target_folder
    duration = args.duration

    if len(file_paths) == 0:
        common.print_error(
            'Error: Could not find any files with this pattern.')

    if not os.path.isdir(target_folder_path):
        print('Create target folder at "{}".'.format(target_folder_path))
        os.makedirs(target_folder_path)

    for file_path in file_paths:
        if not os.path.isfile(file_path):
            print('Warning: "{}" could not be found or is a folder '
                  'Ignore it!'.format(file_path))
            continue

        if not file_path.endswith('.mid'):
            print('Warning: File "{}" does not end with ".mid". '
                  'Ignore it!'.format(file_path))
            continue

        # Read MIDi file and clean up
        score = midi.PrettyMIDI(file_path)
        score.remove_invalid_notes()
        print('➜ Loaded "{}".'.format(file_path))

        # Split MIDI file!
        splits = split_score(score, duration)

        # Generate MIDI files from splits
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        generate_files(base_name, target_folder_path, splits)

        print('')

    print('Done!')


if __name__ == '__main__':
    main()
