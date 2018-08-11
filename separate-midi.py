import argparse

import pretty_midi as midi

import common


# Use these parameters for every part of the score
DEFAULT_INSTRUMENT = 'Acoustic Grand Piano'


def main():
    parser = argparse.ArgumentParser(
        description='Separate all voices from a MIDI file into parts.')
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
    parser.add_argument('--instrument',
                        metavar='name',
                        help='converts parts to given instrument',
                        default=DEFAULT_INSTRUMENT)

    args = parser.parse_args()

    file_paths = common.get_files(args.files)
    target_folder_path = args.target_folder
    instrument = args.instrument

    common.check_target_folder(target_folder_path)

    for file_path in file_paths:
        if common.is_invalid_file(file_path):
            continue

        # Import MIDI file, separate voices
        print('➜ Import file at "{}" ..'.format(file_path))

        # Read MIDi file and clean up
        score = midi.PrettyMIDI(file_path)
        score.remove_invalid_notes()
        print('Loaded "{}".'.format(file_path))

        # Group all notes by start time
        note_by_tick = {}
        note_counter = 0
        max_group_size = 0

        for instrument in score.instruments:
            for note in instrument.notes:
                tick = score.time_to_tick(note.start)
                if tick not in note_by_tick:
                    note_by_tick[tick] = []
                note_by_tick[tick].append(note)
                max_group_size = max(max_group_size, len(note_by_tick[tick]))
                note_counter += 1

        print('Found {} distinguishable start times for {} notes. '
              'Largest chord has {} notes.'.format(len(note_by_tick),
                                                   note_counter,
                                                   max_group_size))

        # Create a new MIDI file
        new_score = midi.PrettyMIDI()

        # Copy data from old score
        new_score.time_signature_changes = score.time_signature_changes
        new_score.key_signature_changes = score.key_signature_changes

        # Create as many parts as we need to keep all voices separate
        for instrument_index in range(0, max_group_size):
            program = midi.instrument_name_to_program(DEFAULT_INSTRUMENT)
            new_instrument = midi.Instrument(program=program)
            new_score.instruments.append(new_instrument)

        # Assign notes to different parts
        for notes in note_by_tick.values():
            for instrument_index, note in enumerate(notes):
                new_score.instruments[instrument_index].notes.append(note)

        for index, instrument in enumerate(new_score.instruments):
            print('{} notes in part {}.'.format(len(instrument.notes),
                                                index + 1))

        # Write result to MIDI file
        new_file_path = common.make_file_path(file_path,
                                              target_folder_path,
                                              suffix='separated')

        # Save result
        new_score.write(new_file_path)

        print('Saved MIDI file at "{}".'.format(new_file_path))
        print('')

    print('Done!')


if __name__ == '__main__':
    main()
