#!/usr/bin/env python3
"""
Crypto Text-to-Speech & Subtitle Generator
Generates deep authoritative financial voiceover + word-aligned subtitles using edge-tts.
"""

import os
import sys
import asyncio
import edge_tts
from datetime import timedelta

VOICE = "en-US-ChristopherNeural"  # Deep authoritative male news voice
RATE = "+10%"                     # Fast punchy financial news pacing

async def generate_audio_and_subtitles(text: str, output_audio: str, output_srt: str):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    submaker = edge_tts.SubMaker()
    
    with open(output_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
                
    # Generate SRT format
    raw_srt = submaker.get_srt()
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(raw_srt)
        
    return output_audio, output_srt

def build_tts(text: str, audio_path: str, srt_path: str):
    asyncio.run(generate_audio_and_subtitles(text, audio_path, srt_path))
    return audio_path, srt_path

if __name__ == "__main__":
    test_text = "WARNING: Bitcoin just dipped to 64,800 dollars, but institutional whales are secretly accumulating."
    build_tts(test_text, "/tmp/test_crypto.mp3", "/tmp/test_crypto.srt")
    print("Generated audio size:", os.path.getsize("/tmp/test_crypto.mp3"))
    print("SRT sample:\n", open("/tmp/test_crypto.srt").read()[:200])
