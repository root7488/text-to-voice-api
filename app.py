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


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "Text to Voice API is running",
        "voices": ["female", "male"]
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
    voice_type = str(data.get("voice", "female")).lower().strip()

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
            "error": "Voice must be male or female"
        }), 400

    try:
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_FOLDER, filename)

        async def generate_audio():
            communicate = edge_tts.Communicate(
                text,
                VOICES[voice_type]
            )
            await communicate.save(filepath)

        asyncio.run(generate_audio())

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
