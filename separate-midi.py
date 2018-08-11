import argparse

import music21 as mc

import common


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

    args = parser.parse_args()

    file_paths = common.get_files(args.files)
    target_folder_path = args.target_folder

    common.check_target_folder(target_folder_path)

    for file_path in file_paths:
        if common.is_invalid_file(file_path):
            continue

        # Import MIDI file, separate voices
        print('➜ Import file at "{}" ..'.format(file_path))
        score = mc.converter.parse(file_path).voicesToParts()

        # Write result to MIDI file
        new_file_path = common.make_file_path(file_path,
                                              target_folder_path,
                                              suffix='separated')

        file = mc.midi.translate.streamToMidiFile(score)
        file.open(new_file_path, 'wb')
        file.write()
        file.close()

        print('Saved MIDI file at "{}".'.format(new_file_path))
        print('')

    print('Done!')


if __name__ == '__main__':
    main()
