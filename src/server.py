#!/usr/bin/env python3
"""
Video Transcribe MCP Server - Transcribe YouTube/Instagram videos to text
"""

import asyncio
import os
import json
import subprocess
import tempfile
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Load environment variables
PROJECT_DIR = Path(__file__).parent.parent
load_dotenv(PROJECT_DIR / ".env")

# Configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru")
TRANSCRIPTS_DIR = Path(os.getenv("TRANSCRIPTS_DIR", "~/Documents/Transcripts")).expanduser()
TEMP_DIR = PROJECT_DIR / "temp"

# Ensure directories exist
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Global whisper model (lazy loaded)
whisper_model = None


def get_whisper_model():
    """Lazy load whisper model"""
    global whisper_model
    if whisper_model is None:
        from faster_whisper import WhisperModel
        # Use GPU if available (for Apple Silicon), otherwise CPU
        whisper_model = WhisperModel(
            WHISPER_MODEL,
            device="auto",
            compute_type="auto"
        )
    return whisper_model


def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename"""
    # Remove invalid chars
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Limit length
    return name[:100].strip()


def detect_platform(url: str) -> str:
    """Detect video platform from URL"""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "instagram.com" in url_lower:
        return "Instagram"
    elif "vk.com" in url_lower or "vkvideo" in url_lower:
        return "VK"
    elif "rutube.ru" in url_lower:
        return "Rutube"
    elif "tiktok.com" in url_lower:
        return "TikTok"
    else:
        return "Video"


def get_video_info(url: str) -> dict:
    """Get video metadata using yt-dlp"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", url],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
            }
    except Exception as e:
        pass
    return {"title": "Unknown", "duration": 0, "uploader": "Unknown"}


def download_audio(url: str, output_path: Path) -> bool:
    """Download audio from video URL using yt-dlp"""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-x",  # Extract audio
                "--audio-format", "mp3",
                "--audio-quality", "0",  # Best quality
                "-o", str(output_path),
                "--no-playlist",  # Single video only
                "--no-warnings",
                url
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )
        return result.returncode == 0
    except Exception as e:
        return False


def format_timestamp(seconds: float) -> str:
    """Format seconds to [MM:SS] or [HH:MM:SS]"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"


def format_duration(seconds: int) -> str:
    """Format duration for display"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def transcribe_audio(audio_path: Path, language: str = "ru") -> list:
    """Transcribe audio file using Whisper"""
    model = get_whisper_model()

    segments, info = model.transcribe(
        str(audio_path),
        language=language if language != "auto" else None,
        beam_size=5,
        word_timestamps=False,
        vad_filter=True,  # Filter out silence
    )

    result = []
    for segment in segments:
        result.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })

    return result


def save_transcript(
    url: str,
    platform: str,
    title: str,
    duration: int,
    segments: list,
    language: str
) -> Path:
    """Save transcript to file"""
    # Generate filename
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_title = sanitize_filename(title)
    filename = f"{date_str}_{platform}_{safe_title}.txt"
    filepath = TRANSCRIPTS_DIR / filename

    # Build content
    lines = [
        f"Источник: {url}",
        f"Платформа: {platform}",
        f"Название: {title}",
        f"Дата транскрипции: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Длительность: {format_duration(duration)}",
        f"Язык: {language}",
        "",
        "=" * 50,
        "",
    ]

    # Add segments with timestamps
    for seg in segments:
        timestamp = format_timestamp(seg["start"])
        lines.append(f"{timestamp} {seg['text']}")

    # Add plain text version at the end
    lines.extend([
        "",
        "=" * 50,
        "ПОЛНЫЙ ТЕКСТ (без таймкодов):",
        "=" * 50,
        "",
        " ".join(seg["text"] for seg in segments)
    ])

    # Write file
    filepath.write_text("\n".join(lines), encoding="utf-8")

    return filepath


# Define MCP tools
TOOLS = [
    Tool(
        name="transcribe_url",
        description="Download and transcribe a video from YouTube, Instagram, or other platforms to text",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Video URL (YouTube, Instagram Reels, VK, TikTok, etc.)",
                },
                "language": {
                    "type": "string",
                    "enum": ["ru", "en", "auto"],
                    "description": "Language of the video (default: ru)",
                },
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="transcribe_file",
        description="Transcribe a local audio/video file to text",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to audio/video file",
                },
                "language": {
                    "type": "string",
                    "enum": ["ru", "en", "auto"],
                    "description": "Language of the audio (default: ru)",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="list_transcripts",
        description="List all saved transcripts",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transcripts to list (default: 20)",
                },
            },
        },
    ),
]


async def handle_transcribe_url(url: str, language: str = None) -> dict:
    """Handle transcribe_url tool call"""
    language = language or DEFAULT_LANGUAGE
    platform = detect_platform(url)

    # Get video info
    info = get_video_info(url)
    title = info["title"]
    duration = info["duration"]

    # Download audio to temp file
    temp_audio = TEMP_DIR / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

    try:
        # Download
        if not download_audio(url, temp_audio):
            return {"error": f"Failed to download audio from {url}. Make sure the video is public."}

        # Find the actual file (yt-dlp might add extension)
        actual_file = None
        for f in TEMP_DIR.glob("audio_*.mp3"):
            actual_file = f
            break

        if not actual_file or not actual_file.exists():
            return {"error": "Audio file not found after download"}

        # Transcribe
        segments = transcribe_audio(actual_file, language)

        if not segments:
            return {"error": "No speech detected in the video"}

        # Save transcript
        filepath = save_transcript(url, platform, title, duration, segments, language)

        # Build response
        full_text = " ".join(seg["text"] for seg in segments)

        return {
            "success": True,
            "platform": platform,
            "title": title,
            "duration": format_duration(duration),
            "language": language,
            "segments_count": len(segments),
            "saved_to": str(filepath),
            "transcript": full_text,
        }

    finally:
        # Cleanup temp files
        for f in TEMP_DIR.glob("audio_*"):
            try:
                f.unlink()
            except:
                pass


async def handle_transcribe_file(file_path: str, language: str = None) -> dict:
    """Handle transcribe_file tool call"""
    language = language or DEFAULT_LANGUAGE
    path = Path(file_path).expanduser()

    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    # Transcribe
    segments = transcribe_audio(path, language)

    if not segments:
        return {"error": "No speech detected in the file"}

    # Calculate duration from segments
    duration = int(segments[-1]["end"]) if segments else 0

    # Save transcript
    filepath = save_transcript(
        f"file://{path}",
        "LocalFile",
        path.stem,
        duration,
        segments,
        language
    )

    # Build response
    full_text = " ".join(seg["text"] for seg in segments)

    return {
        "success": True,
        "file": str(path),
        "duration": format_duration(duration),
        "language": language,
        "segments_count": len(segments),
        "saved_to": str(filepath),
        "transcript": full_text,
    }


async def handle_list_transcripts(limit: int = 20) -> dict:
    """Handle list_transcripts tool call"""
    files = sorted(TRANSCRIPTS_DIR.glob("*.txt"), reverse=True)[:limit]

    transcripts = []
    for f in files:
        transcripts.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        })

    return {
        "transcripts_dir": str(TRANSCRIPTS_DIR),
        "count": len(transcripts),
        "files": transcripts,
    }


async def handle_tool_call(name: str, arguments: dict) -> str:
    """Handle tool calls"""
    try:
        if name == "transcribe_url":
            result = await handle_transcribe_url(
                arguments["url"],
                arguments.get("language"),
            )
        elif name == "transcribe_file":
            result = await handle_transcribe_file(
                arguments["file_path"],
                arguments.get("language"),
            )
        elif name == "list_transcripts":
            result = await handle_list_transcripts(
                arguments.get("limit", 20),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def main():
    """Main entry point"""
    server = Server("video-transcribe-mcp")

    @server.list_tools()
    async def list_tools():
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = await handle_tool_call(name, arguments)
        return [TextContent(type="text", text=result)]

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
