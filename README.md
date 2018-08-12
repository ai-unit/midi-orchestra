# midi-orchestra

Scripts for pre-processing, splitting or evaluating MIDI files for machine learning purposes and dataset generation.

## Example

1. Take a complex, multipart orchestra MIDI score, transform the score into monophonic, separate voices via `separate-midi.py`.

2. Split the score into smaller parts of x seconds for faster processing via `split-midi.py`.

3. Quantize, convert time signature, transpose all notes within a defined interval and reduce the score to only y voices without loosing any information (all possible part combinations get added up, augmenting the dataset) via `preprocess-midi.py`.

4. Visualize the results as piano roll diagrams via `visualize-midi.py`.

## Installation

```
pip install -r requirements.txt
```

## Usage

```
$ python split-midi.py -h
usage: split-midi.py [-h] [--target_folder path] [--duration seconds]
                     path [path ...]

Helper script to split MIDI files into shorter sequences by a fixed duration.

positional arguments:
  path                  path of input files (.mid). accepts * as wildcard

optional arguments:
  -h, --help            show this help message and exit
  --target_folder path  folder path where generated results are stored
  --duration seconds    duration of every slice in seconds
```

```
$ python separate-midi.py -h
usage: separate-midi.py [-h] [--target_folder path] [--instrument name]
                        path [path ...]

Separate all voices from a MIDI file into parts.

positional arguments:
  path                  path of input files (.mid). accepts * as wildcard

optional arguments:
  -h, --help            show this help message and exit
  --target_folder path  folder path where generated results are stored
  --instrument name     converts parts to given instrument
```

```
$ python preprocess-midi.py -h
usage: preprocess-midi.py [-h] [--target_folder path] [--interval_note note]
                          [--interval_low 0-8] [--interval_high 0-8]
                          [--time_signature 4/4] [--instrument name]
                          [--clef treble] [--voice_num 1-32]
                          [--voice_distribution 0.0-1.0 [0.0-1.0 ...]]
                          [--quantization 1-6 [1-6 ...]]
                          [--part_ratio 0.0-1.0]
                          path [path ...]

Preprocess (quantize, simplify, merge ..) and augment complex MIDI files for
machine learning purposes and dataset generation of multipart MIDI scores.

positional arguments:
  path                  path of input files (.mid). accepts * as wildcard

optional arguments:
  -h, --help            show this help message and exit
  --target_folder path  folder path where generated results are stored
  --interval_note note  base note for transpose interval
  --interval_low 0-8    lower end of transpose interval
  --interval_high 0-8   higher end of transpose interval
  --time_signature 4/4  converts score to given time signature
  --instrument name     converts parts to given instrument
  --clef treble         converts parts to given clef
  --voice_num 1-32      converts to this number of parts
  --voice_distribution 0.0-1.0 [0.0-1.0 ...]
                        defines maximum size of alternative options per voice
                        (0.0 - 1.0)
  --quantization 1-6 [1-6 ...]
                        quantize MIDI grid values
  --part_ratio 0.0-1.0  all notes / part notes ratio threshold to remove too
                        sparse parts
```

```
$ python visualize-midi.py -h
usage: visualize-midi.py [-h] [--target_folder path] [--pitch_start 0-127]
                         [--pitch_end 0-127] [--resolution 1-1000]
                         [--width 1-100] [--height 1-100]
                         path [path ...]

Helper script to visualize MIDI files as piano rolls which are saved as .png.

positional arguments:
  path                  path of input files (.mid). accepts * as wildcard

optional arguments:
  -h, --help            show this help message and exit
  --target_folder path  folder path where generated images are stored
  --pitch_start 0-127   midi note range start (y-axis)
  --pitch_end 0-127     midi note range end (y-axis)
  --resolution 1-1000   analysis resolution
  --width 1-100         width of figure (inches)
  --height 1-100        height of figure (inches)
```
