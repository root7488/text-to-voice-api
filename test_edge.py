import asyncio
import edge_tts

async def main():
    print("Starting Edge-TTS test...", flush=True)

    communicate = edge_tts.Communicate(
        text="नमस्कार दोस्तों, यह एक टेस्ट आवाज है।",
        voice="hi-IN-MadhurNeural",
        rate="+0%",
        pitch="+0Hz"
    )

    await communicate.save("/tmp/voice-test.mp3")
    print("SUCCESS: Audio generated!", flush=True)

asyncio.run(main())
