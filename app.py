from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from gtts import gTTS
import os
import uuid

app = Flask(__name__)
CORS(app)

AUDIO_FOLDER = "audio"
os.makedirs(AUDIO_FOLDER, exist_ok=True)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "Text to Voice API is running"
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
    language = str(data.get("language", "hi")).strip()

    if not text:
        return jsonify({
            "success": False,
            "error": "Text is required"
        }), 400

    # Prevent excessively large requests
    if len(text) > 5000:
        return jsonify({
            "success": False,
            "error": "Maximum 5000 characters allowed"
        }), 400

    allowed_languages = ["hi", "en"]

    if language not in allowed_languages:
        return jsonify({
            "success": False,
            "error": "Only Hindi and English are currently supported"
        }), 400

    try:
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_FOLDER, filename)

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(filepath)

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