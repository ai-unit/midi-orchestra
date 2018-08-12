import argparse
import bisect

import pretty_midi as midi

import common


# Use these parameters for every part of the score
DEFAULT_INSTRUMENT = 'Acoustic Grand Piano'


class SortableNote(midi.Note):
    """Introduce a variant of the Note class to make it sortable."""

    def __init__(self, velocity, pitch, start, end):
        super().__init__(velocity, pitch, start, end)

    def __lt__(self, other):
        return self.start < other.start


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

        # Get all notes and sort them by start time
        notes = []
        for instrument in score.instruments:
            for note in instrument.notes:
                # Convert Note to SortableNote
                notes.append(SortableNote(note.velocity,
                                          note.pitch,
                                          note.start,
                                          note.end))
        notes.sort()
        notes_count = len(notes)

        print('Found {} notes in whole score.'.format(notes_count))

        # Separating all notes in parts by checking if they overlap
        parts = [notes]
        part_index_offset = 0
        movement_counter = 0

        while part_index_offset < len(parts):
            part_notes = parts[part_index_offset]
            note_index = 0

            while len(part_notes) > 0 and note_index < len(part_notes):
                next_note_index = note_index + 1
                queue = []

                while (next_note_index < len(part_notes) - 1 and (
                        part_notes[next_note_index].start <=
                        part_notes[note_index].end)):
                    queue.append(next_note_index)
                    next_note_index += 1

                # Move notes which have been stored in a queue
                for index, move_note_index in enumerate(queue):
                    part_index = part_index_offset + index + 1
                    # Create part when it does not exist yet
                    if len(parts) - 1 < part_index:
                        parts.append([])

                    # Move note to part
                    note = part_notes[move_note_index]
                    parts[part_index].append(note)
                    movement_counter += 1

                # Remove notes from previous part
                if len(queue) == 1:
                    del part_notes[queue[0]]
                elif len(queue) > 1:
                    del part_notes[queue[0]:queue[-1]]

                # Start from top when we deleted something
                if len(queue) > 0:
                    note_index = 0
                else:
                    # .. otherwise move on to next note
                    note_index += 1

            part_index_offset += 1

        print('Created {} parts. Moved notes {} times.'.format(
            len(parts), movement_counter))

        # Merge parts when possible
        print('Merging parts ..')
        merged_counter = 0

        for index, part in enumerate(reversed(parts)):
            part_index = len(parts) - index - 1
            queue = []

            for note_index, note in enumerate(part):
                done = False
                other_part_index = part_index - 1

                while not done:
                    if other_part_index < 0:
                        break

                    other_note_index = -1
                    found_free_space = True

                    while True:
                        other_note_index += 1

                        # We reached the end .. nothing found!
                        if other_note_index > len(parts[other_part_index]) - 1:
                            found_free_space = False
                            break

                        other_note = parts[other_part_index][other_note_index]

                        # Is there any overlapping notes?
                        if not (note.end <= other_note.start or
                                note.start >= other_note.end):
                            found_free_space = False
                            break

                        # Stop here since there is nothing more coming.
                        if other_note.start > note.end:
                            break

                    if found_free_space:
                        bisect.insort_left(parts[other_part_index], note)
                        queue.append(note_index)
                        merged_counter += 1
                        done = True
                    else:
                        other_part_index -= 1

            # Delete moved notes from old part
            for index in sorted(queue, reverse=True):
                del part[index]

        print('Done! Moved notes {} times for merging.'.format(merged_counter))

        # Remove empty parts
        remove_parts_queue = []
        for part_index, part in enumerate(parts):
            if len(part) == 0:
                remove_parts_queue.append(part_index)

        for index in sorted(remove_parts_queue, reverse=True):
            del parts[index]

        print('Cleaned up {} empty parts after merging. Now {} parts.'.format(
            len(remove_parts_queue), len(parts)))

        # Create a new MIDI file
        new_score = midi.PrettyMIDI()

        # Copy data from old score
        new_score.time_signature_changes = score.time_signature_changes
        new_score.key_signature_changes = score.key_signature_changes

        # Create as many parts as we need to keep all voices separate
        for instrument_index in range(0, len(parts)):
            program = midi.instrument_name_to_program(DEFAULT_INSTRUMENT)
            new_instrument = midi.Instrument(program=program)
            new_score.instruments.append(new_instrument)

        # Assign notes to different parts
        statistics = []
        for part_index, part in enumerate(parts):
            new_score.instruments[part_index].notes = part
            statistics.append('{0:.2%}'.format(len(part) / notes_count))

        print('Notes per part (in percentage): {}'.format(statistics))

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
