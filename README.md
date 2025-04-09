# CutRallies
A simple video tool for marking rally segments in sports videos.

## Installation

1. Ensure you have Python installed (3.6 or newer)
2. Install required packages:
```
pip install opencv-python pillow numpy
```

## Usage

1. Run the application:
```
python cut_rallies.py
```

2. Click "Load Video" to select a video file
3. Use the following controls to mark rally segments:

### Basic Controls

- **Load Video**: Select a video file to analyze
- **Play/Pause (P)**: Toggle video playback
- **Mark Rally Start (S)**: Mark the beginning of a rally
- **Mark Rally End (D)**: Mark the end of a rally
- **Delete Last Mark (Backspace)**: Remove the last marker
- **Export CSV (E)**: Save all rally markers to a CSV file

### Keyboard Shortcuts

- **S**: Mark rally start
- **D**: Mark rally end
- **P**: Play/Pause video
- **E**: Export to CSV
- **→**: Advance 1 frame
- **←**: Go back 1 frame
- **↑**: Advance 10 frames
- **↓**: Go back 10 frames
- **Backspace**: Delete last marker

## Output

The exported CSV contains the following information for each rally:
- Rally Number
- Start/End Time (HH:MM:SS.mmm)
- Duration
- Start/End Frame numbers
- Start/End time in seconds

## Troubleshooting

If you encounter issues with video playback:
1. Ensure you have the correct codecs installed
2. Try converting your video to MP4 format
3. Check the console output for error messages