# YouTubeCMD

YouTubeCMD is a Windows command-line video player that lets you watch YouTube videos directly inside a CMD-compatible terminal.

It uses:
- `yt-dlp` for YouTube stream extraction
- FFmpeg for video/audio decoding
- ANSI escape sequences
- Unicode half-block characters
- ASCII fallback rendering

The visual output stays inside the terminal. Audio plays through the normal Windows audio device.

---

## What YouTubeCMD Does

YouTubeCMD turns a terminal window into a very basic YouTube player.

You run:

```bat
YouTubeCMD.bat
```

Then you paste a YouTube URL:

```text
YouTube URL: https://www.youtube.com/watch?v=XXXXXXXXXXX
```

YouTubeCMD then:
1. Validates the URL.
2. Extracts playable streams using `yt-dlp`.
3. Starts audio playback.
4. Decodes video frames with FFmpeg.
5. Renders frames inside the terminal using characters.
6. Keeps playback paced to the source FPS.
7. Restores the terminal when you quit.

---

## Important Limitation

A terminal cannot display real video pixels like a graphical player.

YouTubeCMD renders the closest practical representation using:
- ASCII characters
- Unicode blocks
- ANSI colors
- half-block characters

The result is not normal video quality, but it can be surprisingly usable.

---

## Features

- Play YouTube videos inside CMD / Windows Terminal
- Supports normal YouTube watch URLs
- Supports `youtu.be` short URLs
- Supports URLs with extra parameters
- Automatic stream extraction
- No manual stream URL input
- Audio playback through Windows
- Terminal-size adaptation
- Aspect-ratio preservation
- HALF_BLOCK rendering mode
- ASCII compatibility mode
- Optional ANSI color mode
- Pause/resume
- Seek forward/backward
- Volume control
- Restart
- Quality adjustment
- Clean terminal restoration
- Friendly error messages

---

## Requirements

### Operating System
- Windows 10
- Windows 11

### Python
Python 3.10 or newer is required.

Check with:

```bat
python --version
```

If Python is missing, install it from:

```text
https://www.python.org/downloads/
```

During installation, make sure to enable:

```text
Add Python to PATH
```

### FFmpeg
FFmpeg must be installed and available in your system PATH.

Check with:

```bat
ffmpeg -version
```

Recommended installation methods:

```bat
winget install Gyan.FFmpeg
```

or download from the official FFmpeg website.

Do not download random FFmpeg builds from unsafe websites.

---

## Project Structure

```text
YouTubeCMD/
	YouTubeCMD.bat
	requirements.txt
	requirements-dev.txt
	config.json
	src/youtubecmd/
		player.py
		renderer.py
		streams.py
		input_controller.py
		setup.py
		config.py
	scripts/
		make_venv.bat
		check_ffmpeg.bat
		local_render_test.py
	tests/
		test_renderer.py
		test_url_validation.py
		test_config.py
		test_player.py
	docs/PLAN.md
```

---

## How to Run

### Method 1 — Double-click

Double-click:

```text
YouTubeCMD.bat
```

Then paste your YouTube URL.

---

### Method 2 — Command line

Open CMD inside the project folder and run:

```bat
YouTubeCMD.bat
```

Or from another directory:

```bat
path\to\YouTubeCMD\YouTubeCMD.bat
```

The launcher should work from any current directory.

---

## First Run

On first run, YouTubeCMD may:

1. Create a local virtual environment.
2. Install required Python packages.
3. Check FFmpeg.
4. Start the player.

This may take a short time.

---

## Usage

When the player starts, you will see something like:

```text
========================================
YouTubeCMD
YouTube URL:
```

Paste a YouTube URL and press Enter.

Example:

```text
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Then playback should begin.

---

## Controls

| Key | Action |
|---|---|
| `Q` | Quit |
| `Esc` | Quit |
| `Space` | Pause / resume |
| `Left Arrow` | Seek backward 5 seconds |
| `Right Arrow` | Seek forward 5 seconds |
| `Up Arrow` | Volume up |
| `Down Arrow` | Volume down |
| `R` | Restart video |
| `F` | Try fullscreen / maximize console |
| `+` | Increase render quality |
| `-` | Decrease render quality |
| `M` | Cycle renderer mode |

---

## Renderer Modes

### HALF_BLOCK — default

Uses Unicode half-block characters:

```text
▀
```

Each terminal cell represents two vertical pixels.

This gives better vertical resolution than plain ASCII.

Best default mode:

```text
HALF_BLOCK
```

---

### ASCII

Uses brightness-based characters:

```text
@%#*+=-:.
```

The mapping ends with a space character.

This mode is faster and more compatible.

Use ASCII if:
- your terminal is slow
- your PC is weak
- colors look broken
- you want maximum FPS

---

### ANSI_COLOR

Uses ANSI colors where supported.

This may look better, but it can be slower.

Use it only if:
- your terminal supports ANSI colors well
- your PC can handle it
- playback remains smooth

---

## Performance Tips

For the best experience:

1. Use Windows Terminal instead of old legacy CMD.
2. Start with ASCII or HALF_BLOCK grayscale.
3. Do not make the terminal extremely large.
4. Keep source resolution around 360p or 480p.
5. Do not expect real 720p terminal output.
6. Lower quality if playback becomes slow.
7. Close heavy background applications.

---

## Recommended Settings for Low-End PCs

For weaker machines:

```text
Renderer: ASCII
Terminal size: moderate
Quality: lower
Color: grayscale
FPS target: 30
```

If playback is stuttering:
- press `-` to lower quality
- switch to ASCII mode
- reduce terminal size
- avoid true-color mode

---

## Configuration

YouTubeCMD can store user preferences in:

```text
config.json
```

Example:

```json
{
	"renderer_mode": "HALF_BLOCK",
	"quality_level": 1.0,
	"volume": 80,
	"color_mode": "grayscale"
}
```

Supported settings may include:
- renderer mode
- quality level
- volume
- color preference

---

## Troubleshooting

### The launcher says Python is missing

Install Python 3.10+ from:

```text
https://www.python.org/downloads/
```

Make sure to select:

```text
Add Python to PATH
```

Then reopen CMD and try again.

---

### The launcher says FFmpeg is missing

Install FFmpeg and make sure it is in PATH.

Check:

```bat
ffmpeg -version
```

If FFmpeg is installed but not detected, open a new terminal window so PATH can refresh.

---

### Invalid YouTube URL

Make sure the URL is a real YouTube link.

Supported examples:

```text
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://m.youtube.com/watch?v=VIDEO_ID
```

Unsupported or malformed URLs will show:

```text
Invalid YouTube URL.
```

---

### Video cannot be accessed automatically

Some videos cannot be played automatically because of:

- login requirement
- age restriction
- region restriction
- private video
- DRM or platform restriction
- unavailable formats

YouTubeCMD should show a clean error message instead of crashing.

---

### Terminal is too small

If the terminal is too small, YouTubeCMD may show a warning.

If possible, it will continue using the maximum usable area.

For better results:
- enlarge the terminal window
- use Windows Terminal
- reduce quality

---

### Colors look broken

Some terminals do not handle ANSI true color well.

Try:
- ASCII mode
- grayscale HALF_BLOCK mode
- Windows Terminal instead of legacy CMD

---

### Playback is slow or stuttering

Try:
- press `-` to reduce quality
- use ASCII mode
- disable true-color mode
- reduce terminal size
- close other applications
- use a lower source resolution

---

### Audio works but video does not

Possible causes:
- FFmpeg video decode failed
- selected stream format is unavailable
- terminal rendering is too slow
- video URL expired
- network problem

Try:
- restarting the video
- seeking again
- using another video
- checking FFmpeg installation

---

### Video works but audio does not

Possible causes:
- audio device problem
- FFmpeg audio output problem
- selected audio stream unavailable
- system volume muted

Check:
- Windows volume
- application volume
- FFmpeg installation
- another YouTube video

---

## Testing

Install the development dependencies once:

```bat
python -m pip install -r requirements-dev.txt
```

Run the offline unit tests:

```bat
python -m pytest
```

Important test areas:
- URL validation
- renderer sizing
- aspect ratio
- luminance mapping
- ASCII output
- HALF_BLOCK output
- config loading
- terminal cleanup

Run the local renderer preview without YouTube or network access:

```bat
python scripts\local_render_test.py
```

---

## Development Roadmap

### Phase 1 — Bootstrap
- project structure
- launcher
- setup checks
- README

### Phase 2 — Stream Selection
- URL validation
- yt-dlp extraction
- friendly errors

### Phase 3 — Renderer
- terminal detection
- ANSI setup
- ASCII mode
- HALF_BLOCK mode
- cleanup

### Phase 4 — Playback
- FFmpeg raw frames
- frame pacing
- audio playback
- status bar

### Phase 5 — Controls
- pause/resume
- seek
- volume
- restart
- quality controls

### Phase 6 — Hardening
- clean errors
- config persistence
- resize handling
- documentation
- tests

---

## Future Experiments

Possible future improvements:

- C++ native renderer
- Rust native renderer
- low-RAM ASCII mode
- smarter frame dropping
- adaptive quality
- better color quantization
- better terminal capability detection
- better Windows Terminal optimization

These experiments should stay separate until they are stable.

---

## Security Notes

YouTubeCMD should:
- use official or reputable dependencies
- avoid downloading random executables
- avoid installing unknown binaries automatically
- prefer Python packages from PyPI
- prefer FFmpeg from reputable sources

---

## Known Limitations

- Terminal output is not real video pixels.
- True-color rendering can be slow.
- Very large terminal windows can reduce FPS.
- Seeking may take a short time because streams are restarted.
- Some YouTube videos cannot be accessed automatically.
- Perfect frame synchronization is not guaranteed.
- CMD and Windows Terminal behave differently.
- Low-end PCs need lower quality settings.

---

## License

Add your chosen license here.

Example:

```text
MIT License
```