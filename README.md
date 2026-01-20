# Video Transcribe MCP

Transcribe YouTube, Instagram, and other video platforms to text using OpenAI Whisper.

## Features

- **transcribe_url** - Download and transcribe video from URL (YouTube, Instagram, VK, TikTok)
  - **preview_minutes** - Transcribe only first N minutes (for long videos)
- **transcribe_file** - Transcribe local audio/video file
- **list_transcripts** - List saved transcripts

## How it works

```
URL → Download audio only → Whisper AI → Text with timestamps
                ↓
        (deleted after)         → Saved to ~/Documents/Transcripts/
```

No videos stored on your computer - only text transcripts.

## Requirements

- macOS (Apple Silicon or Intel)
- ~3 GB disk space (Whisper model)
- Homebrew

## Setup

### 1. Install system dependencies

```bash
brew install ffmpeg yt-dlp
```

### 2. Clone and setup

```bash
cd ~
git clone https://github.com/egorka23/video-transcribe-mcp.git
cd video-transcribe-mcp
uv venv --python 3.11
source .venv/bin/activate
uv pip install faster-whisper python-dotenv "mcp>=1.0.0"
```

### 3. Configure

```bash
cp .env.example .env
# Edit if needed (defaults are good for Russian)
```

### 4. Add to Claude Code

```bash
claude mcp add video-transcribe -s user \
  -- ~/video-transcribe-mcp/.venv/bin/python ~/video-transcribe-mcp/src/server.py
```

### 5. Restart Claude Code

First transcription will download Whisper model (~3 GB). This happens once.

## Usage

After setup, Claude can:

```
"Transcribe this video: https://youtube.com/watch?v=..."
"Транскрибируй https://instagram.com/reel/..."
"Show my recent transcripts"
```

### Preview Mode (for long videos)

For long videos, preview first 10-15 minutes before full transcription:

```
"Preview first 10 minutes: https://youtube.com/watch?v=..."
"Превью первых 15 минут этого видео"
```

After preview, say "continue" or "продолжай" for full transcription.

### Languages

- `ru` - Russian (default)
- `en` - English
- `auto` - Auto-detect

```
"Transcribe in English: https://youtube.com/..."
"Транскрибируй на английском: ..."
```

## Supported Platforms

| Platform | Support |
|----------|---------|
| YouTube | Full (videos, shorts) |
| Instagram | Reels, IGTV (public only) |
| VK Video | Full |
| TikTok | Full |
| Rutube | Full |
| 1000+ more | Via yt-dlp |

## Transcript Format

Saved to `~/Documents/Transcripts/`:

```
2024-01-19_1530_YouTube_VideoTitle.txt
```

Contains:
- Source URL
- Timestamps for each segment
- Full text without timestamps

## Configuration

Edit `.env`:

```bash
# Whisper model (larger = more accurate, slower)
# Options: tiny, base, small, medium, large-v3
WHISPER_MODEL=large-v3

# Default language
DEFAULT_LANGUAGE=ru

# Transcripts folder
TRANSCRIPTS_DIR=~/Documents/Transcripts
```

## Troubleshooting

**Instagram not working:**
- Only public content works
- Private accounts/reels won't download

**Slow transcription:**
- `large-v3` model is accurate but slow
- For faster (less accurate): change to `medium` or `small`

**Model download stuck:**
- First run downloads ~3 GB
- Check internet connection
