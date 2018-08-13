import argparse
import math

import numpy as np
import pretty_midi as midi

import common


# Transpose all notes between this range
INTERVAL_LOW = 32
INTERVAL_HIGH = 72

# Use these parameters for every part of the score
DEFAULT_BPM = 120
DEFAULT_INSTRUMENT = 'Acoustic Grand Piano'
DEFAULT_TIME_SIGNATURE = (3, 4)

# How many parts our output will contain
VOICE_NUM = 4

# How should the parts be distributed in %
VOICE_DISTRIBUTION = [0.2, 0.3, 0.3, 0.2]

# Parts with less than x percent of all notes get removed
SCORE_PART_RATIO = 0.05

# Keep measures with these time signatures, remove other
VALID_TIME_SIGNATURES = [DEFAULT_TIME_SIGNATURE, (6, 8)]


def get_end_time(score, bpm, time_signature):
    """Gets the normalized duration of a score."""

    # Get the score end time in seconds
    end_time = math.ceil(score.get_end_time() * 10) / 10

    # Calculate how long a measure is in seconds
    beat_time = midi.qpm_to_bpm(60 / bpm, time_signature[0], time_signature[1])
    measure_time = beat_time * time_signature[0]

    # Normalize the end time to a well formed measure
    end_time = end_time + (end_time % measure_time)

    return end_time


def copy_note(note, offset=0):
    """Safely make a new note instance."""

    return midi.Note(pitch=note.pitch,
                     start=note.start + offset,
                     end=note.end + offset,
                     velocity=note.velocity)


def filter_time_signatures(score, valid_time_signatures, bpm, time_signature):
    """Filters notes by time signature."""

    original_end_time = get_end_time(score, bpm, time_signature)

    # Detect times with correct time signatures
    valid_times = []
    valid_time = []

    for signature in score.time_signature_changes:
        is_valid_signature = False

        for valid_signature in valid_time_signatures:
            if (signature.numerator == valid_signature[0] and
                    signature.denominator == valid_signature[1]):
                is_valid_signature = True
                print('Found {}.'.format(signature))

        if is_valid_signature:
            if len(valid_time) == 1:
                # Ignore this valid signature since we already have one.
                continue

            if len(valid_time) == 2:
                # This is already full, save it!
                valid_times.append(valid_time)

            # Keep the start time of this valid time period
            valid_time = [signature.time]

        else:
            # This is the end of a valid period
            if len(valid_time) == 1:
                valid_times.append([valid_time[0], signature.time])
                valid_time = []

    if len(valid_time) == 1:
        valid_times.append([valid_time[0], original_end_time])

    print('Total {} valid time frame(s).'.format(len(valid_times)))

    # Create a new score with only valid time signatures
    new_score = midi.PrettyMIDI(initial_tempo=bpm)

    for instrument in score.instruments:
        new_instrument = midi.Instrument(program=instrument.program)
        for note in instrument.notes:
            offset = 0
            for valid_time in valid_times:
                offset += valid_time[0]
                if not (note.end <= valid_time[0] or
                        note.start >= valid_time[1]):
                    new_instrument.notes.append(copy_note(note, -offset))
        new_score.instruments.append(new_instrument)

    end_time = get_end_time(new_score, bpm, time_signature)
    print('New score has a length of {0:.4} seconds '
          '(original was {1:.4} seconds).'.format(
              end_time, original_end_time))

    if end_time / original_end_time < 0.1:
        print('Warning: A large part of the original score was removed!')

    return new_score


def remove_sparse_parts(score, ratio):
    """Remove parts which are too sparse."""

    original_instruments_count = len(score.instruments)
    original_notes_count = 0
    for instrument in score.instruments:
        original_notes_count += len(instrument.notes)

    removed_instruments = []

    for instrument_index, instrument in enumerate(score.instruments):
        instrument_notes_count = len(instrument.notes)
        if instrument_notes_count == 0:
            instrument_score_ratio = 0
        else:
            instrument_score_ratio = (
                instrument_notes_count / original_notes_count)

        ratio_str = ''
        for i in range(math.ceil(instrument_score_ratio * 100)):
            ratio_str += '='

        print('Part #{0:03d} score: {1:6.2%} {2}'.format(
            instrument_index + 1,
            instrument_score_ratio,
            ratio_str))

        if instrument_score_ratio < ratio:
            removed_instruments.append(instrument_index)

    for instrument_index in reversed(removed_instruments):
        del score.instruments[instrument_index]

    print('Removed {} part(s), now {} given (original had {}).'.format(
        original_instruments_count - len(score.instruments),
        len(score.instruments),
        original_instruments_count))


def identify_ambitus_groups(score, voice_num, voice_distribution):
    """Finds out which parts of the score belong to which ambitus group."""

    print('Identify ambitus groups for all score parts ..')

    # 1. Analyze ambitus for every part
    instrument_intervals = []
    for instrument_index, instrument in enumerate(score.instruments):
        pitches = []
        for note in instrument.notes:
            pitches.append(note.pitch)

        instrument_intervals.append([instrument_index,
                                     min(pitches),
                                     max(pitches)])

    # 2. Identify minimum and maximum ambitus over all parts
    instrument_intervals = np.array(instrument_intervals)
    interval_min = np.min(instrument_intervals[:, 1])
    interval_max = np.max(instrument_intervals[:, 2])
    print('Score ambitus is {} - {} (min - max)!'.format(interval_min,
                                                         interval_max))

    # 3. Calculate closeness for every part to our groups
    scores = []
    interval_total = interval_max - interval_min
    interval_slice = math.ceil(interval_total / voice_num)

    range_min = interval_min - 1
    for voice_index in range(0, voice_num):
        range_min = interval_min + (interval_slice * voice_index) + 1
        range_max = interval_min + (
            interval_slice * voice_index) + interval_slice
        for interval in instrument_intervals:
            instrument_index, instrument_min, instrument_max = interval
            closeness = abs(range_min - instrument_min) + abs(
                range_max - instrument_max)
            closeness = 1 - (closeness / (interval_total * 2))
            scores.append([instrument_index,
                           voice_index,
                           closeness])

    # 4. Group parts based on closeness
    instrument_groups = []
    groups_count = [0 for i in range(0, voice_num)]

    for interval in instrument_intervals:
        # Filter all closeness scores belonging to this part ...
        instrument_index = interval[0]
        instrument_scores = list(filter(lambda i: i[0] == instrument_index,
                                        scores))
        # ... sort them ...
        instrument_scores = sorted(instrument_scores, key=lambda i: i[2],
                                   reverse=True)
        # ... and take the group with the best score.
        group_index = instrument_scores[0][1]
        find_direction = True
        while (groups_count[group_index] / len(instrument_intervals)
               > voice_distribution[group_index]):
            # Change group index when first choice was too full
            if group_index == voice_num - 1:
                find_direction = False
            elif group_index == 0:
                find_direction = True
            group_index += 1 if find_direction else -1

        instrument_groups.append(group_index)
        groups_count[group_index] += 1

    groups_count = np.array(groups_count)

    # 5. Fill up empty spaces
    while len(np.where(groups_count == 0)[0]) > 0:
        empty_group_index = np.where(groups_count == 0)[0][0]
        full_group_index = np.argmax(groups_count)
        instrument_index = np.argwhere(
            instrument_groups == full_group_index).flatten()[0]
        instrument_groups[instrument_index] = empty_group_index
        groups_count[empty_group_index] += 1
        groups_count[full_group_index] -= 1
        print('Empty group {} detected, fill it up with part {}!'.format(
            empty_group_index, instrument_index))

    print('Parts in groups:', instrument_groups)

    return np.array(instrument_groups)


def transpose(score, interval_min, interval_max):
    """Transpose all notes within a given interval."""

    for instrument in score.instruments:
        for note in instrument.notes:
            normalized_pitch = note.pitch % 12
            if note.pitch > interval_max:
                normalized_interval = interval_max % 12
                new_pitch = interval_max - normalized_interval - (
                    12 - normalized_pitch)
            elif note.pitch < interval_min:
                normalized_interval = interval_min % 12
                new_pitch = interval_min + (
                    normalized_interval + normalized_pitch)
            else:
                new_pitch = note.pitch

            note.pitch = new_pitch


def create_combination_tree(options, group_index):
    """Convert all possible combinations into a tree data structure."""

    if len(options) - 1 < group_index:
        return None

    combinations = []

    for option in options[group_index]:
        combinations.append(option)
        results = create_combination_tree(options, group_index + 1)
        if results:
            combinations.append(results)

    return combinations


def traverse_combination_tree(tree, single_combination=[], result=[], depth=0):
    """Traverse a tree to find all possible combinations."""

    if not hasattr(tree, '__len__'):
        return single_combination

    if depth == 0:
        result = []

    if len(tree) == 1:
        result.append(traverse_combination_tree(tree[0],
                                                single_combination + [tree[0]],
                                                result,
                                                depth + 1))

    for i in range(0, len(tree) - 1, 2):
        sub_tree = tree[i + 1]
        if not hasattr(sub_tree, '__len__'):
            for n in tree:
                result.append(
                    traverse_combination_tree(n,
                                              single_combination + [n],
                                              result,
                                              depth + 1))
        else:
            traverse_combination_tree(sub_tree,
                                      single_combination + [tree[i]],
                                      result,
                                      depth + 1)

    return result


warnings = []


def print_warning(text, file_path):
    """Print a warning message to the user and store it for summary."""

    print('Warning: {}\n'.format(text))
    warnings.append([text, file_path])


def main():
    """User interface."""

    parser = argparse.ArgumentParser(
        description='Preprocess (quantize, simplify, merge ..) and augment '
                    'complex MIDI files for machine learning purposes and '
                    'dataset generation of multipart MIDI scores.')
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
    parser.add_argument('--interval_low',
                        metavar='0-127',
                        type=int,
                        help='lower end of transpose interval',
                        choices=range(0, 127),
                        default=INTERVAL_LOW)
    parser.add_argument('--interval_high',
                        metavar='0-127',
                        help='higher end of transpose interval',
                        type=int,
                        choices=range(0, 127),
                        default=INTERVAL_HIGH)
    parser.add_argument('--time_signature',
                        metavar='4/4',
                        type=str,
                        help='converts score to given time signature')
    parser.add_argument('--valid',
                        metavar='3/4',
                        nargs='*',
                        type=str,
                        help='keep these time signatures, remove others')
    parser.add_argument('--instrument',
                        metavar='name',
                        help='converts parts to given instrument',
                        default=DEFAULT_INSTRUMENT)
    parser.add_argument('--voice_num',
                        metavar='1-32',
                        type=int,
                        help='converts to this number of parts',
                        choices=range(1, 32),
                        default=VOICE_NUM)
    parser.add_argument('--bpm',
                        metavar='1-320',
                        type=int,
                        help='global tempo of score',
                        choices=range(1, 320),
                        default=DEFAULT_BPM)
    parser.add_argument('--voice_distribution',
                        metavar='0.0-1.0',
                        nargs='+',
                        type=common.restricted_float,
                        help='defines maximum size of alternative options '
                             'per voice (0.0 - 1.0)',
                        default=VOICE_DISTRIBUTION)
    parser.add_argument('--part_ratio',
                        metavar='0.0-1.0',
                        type=common.restricted_float,
                        help='all notes / part notes ratio threshold '
                             'to remove too sparse parts',
                        default=SCORE_PART_RATIO)

    args = parser.parse_args()

    file_paths = common.get_files(args.files)

    default_bpm = args.bpm
    default_instrument = args.instrument
    interval_high = args.interval_high
    interval_low = args.interval_low
    score_part_ratio = args.part_ratio
    target_folder_path = args.target_folder
    voice_distribution = args.voice_distribution
    voice_num = args.voice_num

    if args.time_signature:
        default_time_signature = [
            int(i) for i in args.time_signature.split('/')]
    else:
        default_time_signature = DEFAULT_TIME_SIGNATURE

    if args.valid:
        valid_time_signatures = []
        for signature in args.valid:
            if '/' in signature:
                valid_time_signatures.append(
                    [int(i) for i in signature.split('/')])
            else:
                common.print_error('Error: Invalid time signature!')
    else:
        valid_time_signatures = VALID_TIME_SIGNATURES

    # Do some health checks before we start
    if interval_high - interval_low < 12:
        common.print_error('Error: Interval range is smaller than an octave!')

    test = 1.0 - np.sum(voice_distribution)
    if test > 0.001 or test < 0:
        common.print_error('Error: voice distribution sum is not 1.0!')

    if len(voice_distribution) != voice_num:
        common.print_error('Error: length of voice distribution is not '
                           'equals the number of voices!')

    common.check_target_folder(target_folder_path)

    for file_path in file_paths:
        if common.is_invalid_file(file_path):
            continue

        # Import MIDI file
        print('➜ Import file at "{}" ..'.format(file_path))

        # Read MIDi file and clean up
        score = midi.PrettyMIDI(file_path)
        score.remove_invalid_notes()
        print('Loaded "{}".'.format(file_path))

        if get_end_time(score,
                        default_bpm,
                        default_time_signature) == 0.0:
            print_warning('Original score is too short! Stop here.',
                          file_path)
            continue

        # Remove invalid time signatures
        temp_score = filter_time_signatures(score,
                                            valid_time_signatures,
                                            default_bpm,
                                            default_time_signature)

        # Remove sparse instruments
        remove_sparse_parts(temp_score, score_part_ratio)

        if len(temp_score.instruments) < voice_num:
            print_warning('Too little voices given! Stop here.',
                          file_path)
            continue

        # Identify ambitus group for every instrument
        groups = identify_ambitus_groups(temp_score,
                                         voice_num,
                                         voice_distribution)

        # Transpose within an interval
        transpose(temp_score, interval_low, interval_high)

        # Check which parts we can combine
        combination_options = []
        for group_index in range(0, voice_num):
            options = np.argwhere(groups == group_index).flatten()
            combination_options.append(options)
            print('Parts {} in group {} (size = {}).'.format(
                options, group_index, len(options)))

        # Build a tree to traverse to find all combinations
        tree = create_combination_tree(combination_options, 0)
        combinations = traverse_combination_tree(tree, single_combination=[])

        print('Found {} possible combinations.'.format(len(combinations)))

        # Prepare a new score with empty parts for every voice
        new_score = midi.PrettyMIDI(initial_tempo=default_bpm)
        temp_end_time = get_end_time(temp_score,
                                     default_bpm,
                                     default_time_signature)

        if temp_end_time < 1.0:
            print_warning('Score is very short, '
                          'maybe due to time signature '
                          'filtering. Skip this!', file_path)
            continue

        new_score.time_signature_changes = [midi.TimeSignature(
            numerator=default_time_signature[0],
            denominator=default_time_signature[1],
            time=0.0)]

        for i in range(0, voice_num):
            program = midi.instrument_name_to_program(default_instrument)
            new_instrument = midi.Instrument(program=program)
            new_score.instruments.append(new_instrument)

        # Add parts in all possible combinations
        for combination_index, combination in enumerate(combinations):
            offset = combination_index * temp_end_time
            for instrument_index, temp_instrument_index in enumerate(
                    reversed(combination)):
                for note in temp_score.instruments[
                        temp_instrument_index].notes:
                    new_score.instruments[instrument_index].notes.append(
                        copy_note(note, offset))

            print('Generated combination #{0:03d}: {1}'.format(
                combination_index + 1, combination))

        # Done!
        new_end_time = get_end_time(new_score,
                                    default_bpm,
                                    default_time_signature)
        print('Generated score with duration {0} seconds. '
              'Data augmentation of {1:.0%}!'.format(
                  round(new_end_time),
                  ((new_end_time / temp_end_time) - 1)))

        # Write result to MIDI file
        new_file_path = common.make_file_path(file_path,
                                              target_folder_path,
                                              suffix='processed')

        new_score.write(new_file_path)

        print('Saved MIDI file at "{}".'.format(new_file_path))
        print('')

    if len(warnings) > 0:
        print('Warnings given:')
        for warning in warnings:
            print('* "{}" in "{}".'.format(warning[0], warning[1]))
        print('')

    print('Done!')


if __name__ == '__main__':
    main()
