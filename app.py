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

# Emotion presets
# These modify speaking rate, pitch and volume.
EMOTIONS = {
    "normal": {
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%"
    },
    "happy": {
        "rate": "+12%",
        "pitch": "+8Hz",
        "volume": "+5%"
    },
    "sad": {
        "rate": "-15%",
        "pitch": "-8Hz",
        "volume": "-5%"
    },
    "angry": {
        "rate": "+15%",
        "pitch": "+5Hz",
        "volume": "+10%"
    },
    "fear": {
        "rate": "+8%",
        "pitch": "+12Hz",
        "volume": "-3%"
    },
    "excited": {
        "rate": "+20%",
        "pitch": "+10Hz",
        "volume": "+8%"
    }
}


def combine_percent(base_value, emotion_value):
    base = int(base_value.replace("%", ""))
    emotion = int(emotion_value.replace("%", ""))

    total = base + emotion

    if total > 50:
        total = 50
    elif total < -50:
        total = -50

    return f"{total:+d}%"


def combine_pitch(base_value, emotion_value):
    base = int(base_value.replace("Hz", ""))
    emotion = int(emotion_value.replace("Hz", ""))

    total = base + emotion

    if total > 30:
        total = 30
    elif total < -30:
        total = -30

    return f"{total:+d}Hz"


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "Text to Voice API is running",
        "voices": list(VOICES.keys()),
        "speeds": list(SPEEDS.keys()),
        "pitches": list(PITCHES.keys()),
        "emotions": list(EMOTIONS.keys())
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
    voice_type = str(data.get("voice", "female")).strip().lower()
    speed_type = str(data.get("speed", "normal")).strip().lower()
    pitch_type = str(data.get("pitch", "normal")).strip().lower()
    emotion_type = str(data.get("emotion", "normal")).strip().lower()

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

    if emotion_type not in EMOTIONS:
        return jsonify({
            "success": False,
            "error": "Invalid emotion"
        }), 400

    voice = VOICES[voice_type]

    emotion = EMOTIONS[emotion_type]

    rate = combine_percent(
        SPEEDS[speed_type],
        emotion["rate"]
    )

    pitch = combine_pitch(
        PITCHES[pitch_type],
        emotion["pitch"]
    )

    volume = emotion["volume"]

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)

    async def generate_voice():

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume
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
