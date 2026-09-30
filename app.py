from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import os
import re
import uuid

from pydub import AudioSegment
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

AUDIO_FOLDER = "audio"
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# FFmpeg supplied by imageio-ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()


VOICES = {
    "female": "hi-IN-SwaraNeural",
    "male": "hi-IN-MadhurNeural"
}


SPEEDS = {
    "slow": -20,
    "normal": 0,
    "fast": 20
}


PITCHES = {
    "low": -10,
    "normal": 0,
    "high": 10
}


EMOTIONS = {

    "normal": {
        "rate": 0,
        "pitch": 0,
        "volume": 0
    },

    "happy": {
        "rate": 12,
        "pitch": 8,
        "volume": 5
    },

    "sad": {
        "rate": -15,
        "pitch": -8,
        "volume": -5
    },

    "angry": {
        "rate": 15,
        "pitch": 5,
        "volume": 10
    },

    "fear": {
        "rate": 8,
        "pitch": 12,
        "volume": -3
    },

    "excited": {
        "rate": 20,
        "pitch": 10,
        "volume": 8
    }
}


# -------------------------------------------------
# AUTO EMOTION WORDS
# -------------------------------------------------

EMOTION_WORDS = {

    "happy": [
        "खुश", "खुशी", "मुस्कुर", "हँस", "हंस",
        "प्यार", "प्रेम", "सुंदर", "खूबसूरत",
        "आनंद", "बधाई", "सफल", "जीत",
        "happy", "love", "smile", "beautiful",
        "wonderful", "joy"
    ],

    "sad": [
        "दुख", "दुःख", "दुखी", "उदास",
        "रोना", "रोया", "रोई", "आँसू", "आंसू",
        "अकेला", "अकेली", "मौत", "मर गया",
        "खो दिया", "बिछड़",
        "sad", "cry", "alone", "death",
        "pain", "sorry"
    ],

    "angry": [
        "गुस्सा", "क्रोध", "नफरत",
        "चुप रहो", "बंद करो", "हिम्मत कैसे",
        "ऐसा क्यों", "गलत किया",
        "angry", "hate", "stop",
        "shut up"
    ],

    "fear": [
        "डर", "डरा", "डरी", "भय",
        "खतरा", "बचाओ", "भूत",
        "अचानक", "चीख", "कांप",
        "fear", "scared", "danger",
        "help", "ghost"
    ],

    "excited": [
        "वाह", "कमाल", "शानदार",
        "बहुत बढ़िया", "जल्दी", "यकीन नहीं",
        "जीत गए", "मजा आ गया",
        "wow", "amazing", "awesome",
        "excited", "fantastic"
    ]
}


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def detect_emotion(sentence):

    text = sentence.lower()

    scores = {
        "happy": 0,
        "sad": 0,
        "angry": 0,
        "fear": 0,
        "excited": 0
    }

    for emotion, words in EMOTION_WORDS.items():

        for word in words:

            if word in text:
                scores[emotion] += 1

    # Punctuation also gives useful clues
    exclamation_count = sentence.count("!")

    if exclamation_count > 0:
        scores["excited"] += 1

    if exclamation_count >= 2:
        scores["excited"] += 1

    # Choose strongest detected emotion
    highest_emotion = max(scores, key=scores.get)

    if scores[highest_emotion] == 0:
        return "normal"

    return highest_emotion


def split_sentences(text):

    parts = re.split(
        r'(?<=[।.!?])\s+|\n+',
        text.strip()
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def format_rate(value):
    value = clamp(value, -50, 50)
    return f"{value:+d}%"


def format_pitch(value):
    value = clamp(value, -30, 30)
    return f"{value:+d}Hz"


def format_volume(value):
    value = clamp(value, -50, 50)
    return f"{value:+d}%"


async def create_segment(
    text,
    voice,
    rate,
    pitch,
    volume,
    filepath
):

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume
    )

    await communicate.save(filepath)


@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "success": True,

        "message": "Text to Voice API with Auto Emotion is running",

        "voices": list(VOICES.keys()),

        "speeds": list(SPEEDS.keys()),

        "pitches": list(PITCHES.keys()),

        "emotions": [
            "auto",
            "normal",
            "happy",
            "sad",
            "angry",
            "fear",
            "excited"
        ]

    })


@app.route("/tts", methods=["POST"])
def text_to_speech():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "error": "JSON data is required"
        }), 400


    text = str(
        data.get("text", "")
    ).strip()


    voice_type = str(
        data.get("voice", "female")
    ).strip().lower()


    speed_type = str(
        data.get("speed", "normal")
    ).strip().lower()


    pitch_type = str(
        data.get("pitch", "normal")
    ).strip().lower()


    emotion_type = str(
        data.get("emotion", "auto")
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


    allowed_emotions = [
        "auto",
        "normal",
        "happy",
        "sad",
        "angry",
        "fear",
        "excited"
    ]


    if emotion_type not in allowed_emotions:

        return jsonify({
            "success": False,
            "error": "Invalid emotion"
        }), 400


    voice = VOICES[voice_type]

    base_speed = SPEEDS[speed_type]
    base_pitch = PITCHES[pitch_type]

    job_id = uuid.uuid4().hex

    final_file = os.path.join(
        AUDIO_FOLDER,
        f"{job_id}.mp3"
    )


    try:

        sentences = split_sentences(text)

        final_audio = AudioSegment.empty()

        segment_files = []


        for index, sentence in enumerate(sentences):

            # AUTO detects each sentence separately
            if emotion_type == "auto":

                detected_emotion = detect_emotion(sentence)

            else:

                detected_emotion = emotion_type


            emotion_settings = EMOTIONS[detected_emotion]


            final_rate = format_rate(
                base_speed +
                emotion_settings["rate"]
            )


            final_pitch = format_pitch(
                base_pitch +
                emotion_settings["pitch"]
            )


            final_volume = format_volume(
                emotion_settings["volume"]
            )


            segment_file = os.path.join(
                AUDIO_FOLDER,
                f"{job_id}_{index}.mp3"
            )

            segment_files.append(segment_file)


            asyncio.run(
                create_segment(
                    sentence,
                    voice,
                    final_rate,
                    final_pitch,
                    final_volume,
                    segment_file
                )
            )


            segment_audio = AudioSegment.from_file(
                segment_file,
                format="mp3"
            )


            final_audio += segment_audio

            # Small natural pause between sentences
            final_audio += AudioSegment.silent(
                duration=180
            )


        final_audio.export(
            final_file,
            format="mp3",
            bitrate="128k"
        )


        # Delete temporary sentence files
        for segment_file in segment_files:

            try:
                os.remove(segment_file)
            except:
                pass


        return send_file(
            final_file,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="voice.mp3"
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
