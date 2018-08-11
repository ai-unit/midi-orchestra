import argparse
import glob
import math
import os

import music21 as mc
import numpy as np

import common


# Transpose all notes between this range
INTERVAL_NOTE = 'C'
INTERVAL_LOW = 3
INTERVAL_HIGH = 5

# Use these parameters for every part of the score
DEFAULT_TIME_SIGNATURE = '4/4'
DEFAULT_INSTRUMENT = 'piano'
DEFAULT_CLEF = 'treble'

# Quantize MIDI data before processing
QUANTIZATION = [4, 3]

# How many parts our output will contain
VOICE_NUM = 5

# How should the parts be distributed in %
VOICE_DISTRIBUTION = [0.1, 0.2, 0.3, 0.2, 0.2]

# Parts with less than x percent of all notes get removed
SCORE_PART_RATIO = 0.015


def identify_instrument_name(stream):
    """Returns the instrument name of this part."""

    instruments = stream.getElementsByClass(mc.instrument.Instrument)
    if len(instruments) > 0 and instruments[0].instrumentName is not None:
        return instruments[0].instrumentName
    return 'Undefined'


def remove_sparse_parts(score, ratio):
    """Remove parts which are too sparse."""

    original_parts_count = len(score)
    original_notes_count = len(score.flat.notes)
    removed_instruments = []

    for part in score:
        part_notes_count = len(part.flat.notes)
        if part_notes_count == 0:
            part_score_ratio = 0
        else:
            part_score_ratio = (part_notes_count / original_notes_count)

        name = identify_instrument_name(part)

        print('Part "{0}" with a note ratio score of {1:.2%}'.format(
            name, part_score_ratio))

        if part_score_ratio < ratio:
            removed_instruments.append(name)
            score.remove(part)

    print('Removed {} part(s): {}, now {} given (original had {}).'.format(
        original_parts_count - len(score),
        removed_instruments,
        len(score),
        original_parts_count))


def identify_ambitus_groups(score, voice_num, voice_distribution):
    """Finds out which parts of the score belong to which ambitus group."""

    print('Identify ambitus groups for all score parts ..')

    # 1. Analyze ambitus for every part
    part_intervals = []
    for part_index, part in enumerate(score):
        interval = mc.analysis.discrete.Ambitus().getSolution(part)
        part_intervals.append([part_index,
                               interval.noteStart.diatonicNoteNum,
                               interval.noteEnd.diatonicNoteNum])

    # 2. Identify minimum and maximum ambitus over all parts
    part_intervals = np.array(part_intervals)
    interval_min = np.min(part_intervals[:, 1])
    interval_max = np.max(part_intervals[:, 2])
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
        for part_interval in part_intervals:
            part_index, part_min, part_max = part_interval
            closeness = abs(range_min - part_min) + abs(range_max - part_max)
            closeness = 1 - (closeness / (interval_total * 2))
            scores.append([part_index,
                           voice_index,
                           closeness])

    # 4. Group parts based on closeness
    part_groups = []
    groups_count = [0 for i in range(0, voice_num)]

    for part_interval in part_intervals:
        # Filter all closeness scores belonging to this part ...
        part_index = part_interval[0]
        part_scores = list(filter(lambda i: i[0] == part_index, scores))
        # ... sort them ...
        part_scores = sorted(part_scores, key=lambda i: i[2], reverse=True)
        # ... and take the group with the best score.
        group_index = part_scores[0][1]
        find_direction = True
        while (groups_count[group_index] / len(part_intervals)
               > voice_distribution[group_index]):
            # Change group index when first choice was too full
            if group_index == voice_num - 1:
                find_direction = False
            elif group_index == 0:
                find_direction = True
            group_index += 1 if find_direction else -1

        part_groups.append(group_index)
        groups_count[group_index] += 1
    print('Parts in groups:', part_groups)

    return np.array(part_groups)


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


def generate_note_from_pitch(old_pitch, note, low, high):
    """Take a pitch object, transpose and generate a new note from it."""

    # Fit within interval range
    new_pitch = old_pitch.transposeAboveTarget(
        mc.pitch.Pitch(name=note, octave=low))
    new_pitch = new_pitch.transposeBelowTarget(
        mc.pitch.Pitch(name=note, octave=high))

    # Choose the most commonly used enharmonic spelling
    new_pitch = new_pitch.simplifyEnharmonic(mostCommon=True)

    new_note = mc.note.Note(name=new_pitch.name,
                            octave=new_pitch.octave)

    return new_note


def clean_copy_element(element, note, low, high):
    """Safely and cleanly copy a note or rest."""

    if element.isNote:
        new_element = generate_note_from_pitch(element.pitch,
                                               note,
                                               low,
                                               high)
    elif element.isChord:
        new_element = generate_note_from_pitch(element.pitches[0],
                                               note,
                                               low,
                                               high)
    elif element.isRest:
        new_element = mc.note.Rest()

    new_element.quarterLength = element.quarterLength
    new_element.offset = element.offset

    return new_element


def create_default_part(instrument, time_signature, clef):
    """Creates a default part."""

    part = mc.stream.Part()

    # Set default instrument, time signature and clef
    part.insert(0, mc.instrument.fromString(instrument))
    part.insert(0, mc.meter.TimeSignature(time_signature))
    part.insert(0, mc.clef.clefFromString(clef))

    return part


def clean_copy_measure(measure, relative_measure_index, duration,
                       note, low, high):
    """Cleanly creates a new measure based on given one."""

    new_measure = mc.stream.Measure()
    new_measure.leftBarline = (
        'light-light' if relative_measure_index == 1 else None)
    new_measure.rightBarline = None

    if measure is not None:
        # Add all notes and rests from given measure
        for element in measure.notesAndRests:
            new_measure.append(clean_copy_element(element,
                                                  note,
                                                  low,
                                                  high))
    else:
        # Insert full rest if given measure does not exist
        new_rest = mc.note.Rest()
        new_rest.duration = duration
        new_measure.append(new_rest)

    return new_measure


def count_measures(part):
    """Returns the number of measures in given part."""

    return len(part.getElementsByClass(mc.stream.Measure))


def max_measures(score):
    """Find part with the highest amount of measures."""

    return max([count_measures(part) for part in score])


def main():
    """
    User interface.

    For machine learning applications we are interested in
    preprocessing MIDI files of different orchestra works
    into a simplified, standardized format:

    * Quantize notes
    * Transpose all notes (octaves) within a fixed range
    * Convert parts to one time signature
    * Remove parts which are too sparse
    * Reduce all parts to a fixed number

    Through part reduction we deal with unused material,
    we use this material to generate new score material,
    changing the original score but keeping the "style"
    of the composition.
    """

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
    parser.add_argument('--interval_note',
                        metavar='note',
                        help='base note for transpose interval',
                        choices=['C', 'D', 'E', 'F', 'G', 'A', 'B'],
                        default=INTERVAL_NOTE)
    parser.add_argument('--interval_low',
                        metavar='0-8',
                        type=int,
                        help='lower end of transpose interval',
                        choices=range(0, 8),
                        default=INTERVAL_LOW)
    parser.add_argument('--interval_high',
                        metavar='0-8',
                        help='higher end of transpose interval',
                        type=int,
                        choices=range(0, 8),
                        default=INTERVAL_HIGH)
    parser.add_argument('--time_signature',
                        metavar='4/4',
                        type=str,
                        help='converts score to given time signature',
                        default=DEFAULT_TIME_SIGNATURE)
    parser.add_argument('--instrument',
                        metavar='name',
                        help='converts parts to given instrument',
                        default=DEFAULT_INSTRUMENT)
    parser.add_argument('--clef',
                        metavar='treble',
                        help='converts parts to given clef',
                        default=DEFAULT_CLEF)
    parser.add_argument('--voice_num',
                        metavar='1-32',
                        help='converts to this number of parts',
                        choices=range(1, 32),
                        default=VOICE_NUM)
    parser.add_argument('--voice_distribution',
                        metavar='0.0-1.0',
                        nargs='+',
                        type=common.restricted_float,
                        help='defines maximum size of alternative options '
                             'per voice (0.0 - 1.0)',
                        default=VOICE_DISTRIBUTION)
    parser.add_argument('--quantization',
                        metavar='1-6',
                        nargs='+',
                        type=int,
                        help='quantize MIDI grid values',
                        choices=range(1, 6),
                        default=QUANTIZATION)
    parser.add_argument('--part_ratio',
                        metavar='0.0-1.0',
                        type=common.restricted_float,
                        help='all notes / part notes ratio threshold '
                             'to remove too sparse parts',
                        default=SCORE_PART_RATIO)

    args = parser.parse_args()

    file_paths = (
        glob.glob(args.files) if isinstance(args.files, str) else args.files)

    default_clef = args.clef
    default_instrument = args.instrument
    default_time_signature = args.time_signature
    interval_high = args.interval_high
    interval_low = args.interval_low
    interval_note = args.interval_note
    quantization = args.quantization
    score_part_ratio = args.part_ratio
    target_folder_path = args.target_folder
    voice_distribution = args.voice_distribution
    voice_num = args.voice_num

    # Do some health checks before we start
    if interval_high < interval_low:
        common.print_error('Error: Interval range is smaller than 0!')

    test = 1.0 - np.sum(voice_distribution)
    if test > 0.001 or test < 0:
        common.print_error('Error: voice distribution sum is not 1.0!')

    if len(voice_distribution) != voice_num:
        common.print_error('Error: length of voice distribution is not '
                           'equals the number of voices!')

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

        # Import MIDI file
        print('➜ Import file at "{}" ..'.format(file_path))
        score = mc.converter.parse(file_path)

        if len(score.flat.notesAndRests) > 10000:
            print('Warning: This is a rather large MIDI file and might '
                  'take some time to process!')

        # Quantize MIDI data
        print('Quantize ..')
        score.quantize(quantization,
                       processOffsets=True,
                       processDurations=True,
                       inPlace=True)

        # Clean up
        print('Remove sparse parts ..')
        remove_sparse_parts(score,
                            score_part_ratio)

        # Identify ambitus group for every part
        part_groups = identify_ambitus_groups(score,
                                              voice_num,
                                              voice_distribution)

        # Check which parts we can combine
        combination_options = []
        is_cancelled = False
        for group_index in range(0, voice_num):
            options = np.argwhere(part_groups == group_index).flatten()
            combination_options.append(options)
            print('Parts {} in group {} (size = {}).'.format(
                options, group_index, len(options)))
            if len(options) == 0:
                print(
                    'Warning: Empty combination group detected! '
                    'Too little parts? Cancel process here!')
                is_cancelled = True
                break

        if is_cancelled:
            print('')
            continue

        # Build a tree to traverse to find all combinations
        tree = create_combination_tree(combination_options, 0)
        combinations = traverse_combination_tree(tree, single_combination=[])

        print('Found {} possible combinations.'.format(len(combinations)))

        # Prepare temporary score
        temp_score = mc.stream.Score()

        # Convert all parts of score to new score
        for part_index, part in enumerate(score):
            new_part = create_default_part(default_instrument,
                                           default_time_signature,
                                           default_clef)

            # Get group this part belongs to
            group_index = part_groups[part_index]

            # Get instrument name for this part for debugging
            instrument_name = identify_instrument_name(part)
            print('Convert part "{}" in group {} with {} notes.'.format(
                instrument_name, group_index, len(part.flat.notes)))

            # Convert notes and rests
            for element in part.flat.notesAndRests:
                new_part.append(clean_copy_element(element,
                                                   interval_note,
                                                   interval_low,
                                                   interval_high))

            temp_score.insert(0, new_part)

        print('Finalize temporary score ..')
        temp_score.makeNotation(inPlace=True)
        print('Done with temporary score!')

        # Calculate longest part in measures
        measures_total = max_measures(temp_score)
        measure_duration = temp_score[0].measure(1).barDuration
        print('Longest part has {} measures (length = {} quarters).'.format(
            measures_total,
            measure_duration.quarterLength))

        # Prepare a new score with empty parts for every voice
        new_score = mc.stream.Score()
        for i in range(0, voice_num):
            new_part = create_default_part(default_instrument,
                                           default_time_signature,
                                           default_clef)
            new_score.insert(0, new_part)

        # Add parts in all possible combinations
        for combination_index, combination in enumerate(combinations):
            for relative_measure_index in range(1, measures_total + 1):
                measure_index = relative_measure_index + (
                    combination_index * measures_total)
                offset = measure_duration.quarterLength * (measure_index - 1)
                for part_index, temp_part_index in enumerate(
                        reversed(combination)):
                    measure = temp_score[temp_part_index].measure(
                        relative_measure_index)
                    new_score[part_index].insert(
                        offset,
                        clean_copy_measure(measure,
                                           relative_measure_index,
                                           measure_duration,
                                           interval_note,
                                           interval_low,
                                           interval_high))
            print('Generated combination {} #{}.'.format(
                combination, combination_index + 1))

        # Finalize!
        print('Finalize score ..')
        new_score.makeNotation(inPlace=True)

        new_measures_total = max_measures(new_score)
        print('Generated score with {} measures. '
              'Data augmentation of {}%!'.format(
                  new_measures_total,
                  ((new_measures_total / measures_total) - 1) * 100))

        # Write result to MIDI file
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        new_file_name = '{}-processed.mid'.format(base_name)
        new_file_path = os.path.join(target_folder_path, new_file_name)

        file = mc.midi.translate.streamToMidiFile(new_score)
        file.open(new_file_path, 'wb')
        file.write()
        file.close()

        print('Saved MIDI file at "{}".'.format(new_file_path))
        print('')

    print('Done!')


if __name__ == '__main__':
    main()
