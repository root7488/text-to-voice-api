from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import os
import uuid

app = Flask(__name__)
CORS(app)

AUDIO_FOLDER = "audio"
os.makedirs(AUDIO_FOLDER, exist_ok=True)

VOICES = {
    "female": "hi-IN-SwaraNeural",
    "male": "hi-IN-MadhurNeural"
}

SPEEDS = {
    "slow": "-20%",
    "normal": "+0%",
    "fast": "+20%"
}

PITCHES = {
    "low": "-10Hz",
    "normal": "+0Hz",
    "high": "+10Hz"
}


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "Text to Voice API is running",
        "voices": list(VOICES.keys()),
        "speeds": list(SPEEDS.keys()),
        "pitches": list(PITCHES.keys())
    })


@app.route("/tts", methods=["POST"])
def text_to_speech():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "JSON data is required"
        }), 400

    text = str(data.get("text", "")).strip()

    voice_type = str(
        data.get("voice", "female")
    ).strip().lower()

    speed_type = str(
        data.get("speed", "normal")
    ).strip().lower()

    pitch_type = str(
        data.get("pitch", "normal")
    ).strip().lower()

    if not text:
        return jsonify({
            "success": False,
            "error": "Text is required"
        }), 400

    if len(text) > 5000:
        return jsonify({
            "success": False,
            "error": "Maximum 5000 characters allowed"
        }), 400

    if voice_type not in VOICES:
        return jsonify({
            "success": False,
            "error": "Invalid voice"
        }), 400

    if speed_type not in SPEEDS:
        return jsonify({
            "success": False,
            "error": "Invalid speed"
        }), 400

    if pitch_type not in PITCHES:
        return jsonify({
            "success": False,
            "error": "Invalid pitch"
        }), 400

    voice = VOICES[voice_type]
    rate = SPEEDS[speed_type]
    pitch = PITCHES[pitch_type]

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)

    async def generate_voice():

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch
        )

        await communicate.save(filepath)

    try:

        asyncio.run(generate_voice())

        return send_file(
            filepath,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name=filename
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
