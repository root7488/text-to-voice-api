from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import os
import re
import uuid
import logging
from edge_tts.exceptions import NoAudioReceived
from pydub import AudioSegment
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)
app.logger.setLevel(logging.INFO)
MAX_CHARACTERS = 10000
AUDIO_FOLDER = 'audio'
os.makedirs(AUDIO_FOLDER, exist_ok=True)
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

VOICES = {'female': 'hi-IN-SwaraNeural', 'male': 'hi-IN-MadhurNeural'}
SPEEDS = {'slow': -20, 'normal': 0, 'fast': 20}
PITCHES = {'low': -10, 'normal': 0, 'high': 10}
# Style variants share the same two Hindi voice identities.
VOICE_STYLES = {
    'male1': ('male', 0, 0), 'male2': ('male', -8, -22), 'male3': ('male', 10, 12),
    'female1': ('female', 0, 0), 'female2': ('female', -9, -8), 'female3': ('female', 9, 16),
}
ROLE_STYLES = {'पापा':'male2','पिता':'male2','दादा':'male2','नाना':'male2', 'बेटा':'male3','लड़का':'male3','भाई':'male3', 'मम्मी':'female1','माँ':'female1','मां':'female1','माता':'female1','दादी':'female2','नानी':'female2','बेटी':'female3','लड़की':'female3','बहन':'female3'}

# Manual story controls: offsets in percentage points (rate) and Hz (pitch).
# Accepted role labels match the explicit role detector in story_chunks().
STORY_ROLES = ['पापा', 'मम्मी', 'बेटा', 'बेटी', 'दादा', 'दादी']
ROLE_ALIASES = {'पिता':'पापा','डैडी':'पापा','डैड':'पापा','बाप':'पापा',
                'माँ':'मम्मी','मां':'मम्मी','माता':'मम्मी',
                'लड़का':'बेटा','भाई':'बेटा','लड़की':'बेटी','बहन':'बेटी',
                'नाना':'दादा','नानी':'दादी'}

EMOTIONS = {
    'normal': {'rate': 0, 'pitch': 0, 'volume': 0},
    'happy': {'rate': 12, 'pitch': 8, 'volume': 5},
    'sad': {'rate': -15, 'pitch': -8, 'volume': -5},
    'angry': {'rate': 15, 'pitch': 5, 'volume': 10},
    'fear': {'rate': 8, 'pitch': 12, 'volume': -3},
    'excited': {'rate': 20, 'pitch': 10, 'volume': 8},
    'loving': {'rate': -8, 'pitch': 5, 'volume': -2},
}
EMOTION_WORDS = {
    'happy': ['खुश', 'खुशी', 'मुस्कुर', 'हँस', 'हंस', 'प्यार', 'प्रेम', 'सुंदर', 'खूबसूरत', 'आनंद', 'बधाई', 'सफल', 'जीत', 'happy', 'love', 'smile', 'beautiful', 'wonderful', 'joy'],
    'sad': ['दुख', 'दुःख', 'दुखी', 'उदास', 'रोना', 'रोया', 'रोई', 'आँसू', 'आंसू', 'अकेला', 'अकेली', 'मौत', 'मर गया', 'खो दिया', 'बिछड़', 'sad', 'cry', 'alone', 'death', 'pain', 'sorry'],
    'angry': ['गुस्सा', 'क्रोध', 'नफरत', 'चुप रहो', 'बंद करो', 'हिम्मत कैसे', 'ऐसा क्यों', 'गलत किया', 'angry', 'hate', 'stop', 'shut up'],
    'fear': ['डर', 'डरा', 'डरी', 'भय', 'खतरा', 'बचाओ', 'भूत', 'अचानक', 'चीख', 'कांप', 'fear', 'scared', 'danger', 'help', 'ghost'],
    'excited': ['वाह', 'कमाल', 'शानदार', 'बहुत बढ़िया', 'जल्दी', 'यकीन नहीं', 'जीत गए', 'मजा आ गया', 'wow', 'amazing', 'awesome', 'excited', 'fantastic'],
    'loving': ['प्यार से', 'स्नेह से', 'दुलार', 'ममता', 'lovingly', 'gently'],
}

# Explicit family roles are more reliable than guessing gender from arbitrary names.
ROLE_GENDERS = {
    'पापा': 'male', 'पिता': 'male', 'बाप': 'male', 'डैडी': 'male', 'डैड': 'male',
    'बेटा': 'male', 'लड़का': 'male', 'भाई': 'male', 'दादा': 'male', 'नाना': 'male',
    'चाचा': 'male', 'मामा': 'male', 'अंकल': 'male', 'पति': 'male',
    'मम्मी': 'female', 'माँ': 'female', 'मां': 'female', 'माता': 'female',
    'बेटी': 'female', 'लड़की': 'female', 'बहन': 'female', 'दादी': 'female',
    'नानी': 'female', 'चाची': 'female', 'मामी': 'female', 'आंटी': 'female', 'पत्नी': 'female',
}
ROLE_PATTERN = re.compile('|'.join(re.escape(x) for x in sorted(ROLE_GENDERS, key=len, reverse=True)))
SPEECH_PATTERN = re.compile(r'(?:ने\s+)?(?:गुस्से\s+में\s+|डरते\s+हुए\s+|खुशी\s+से\s+|प्यार\s+से\s+|धीरे\s+से\s+|रोते\s+हुए\s+)?(?:कहा|बोला|बोली|पूछा|चिल्लाया|चिल्लाई|जवाब\s+दिया|समझाया|बताया|कहने\s+लगा|कहने\s+लगी)')
QUOTES = re.compile(r'["“‘](.*?)["”’]', re.DOTALL)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def detect_emotion(sentence):
    text = sentence.lower()
    scores = {key: 0 for key in EMOTION_WORDS}
    for emotion, words in EMOTION_WORDS.items():
        for word in words:
            if word in text:
                scores[emotion] += 1
    if sentence.count('!'):
        scores['excited'] += 1
    if sentence.count('!') >= 2:
        scores['excited'] += 1
    highest = max(scores, key=scores.get)
    return highest if scores[highest] else 'normal'


def split_sentences(text):
    """Split long inputs at natural punctuation and safe word boundaries."""
    chunks = []
    for paragraph in re.split(r'\n+', text.strip()):
        for sentence in re.split(r'(?<=[।.!?])\s*', paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            # A long paragraph without full stops still needs manageable TTS requests.
            while len(sentence) > 650:
                candidates = [sentence.rfind(mark, 0, 650) for mark in (' ', ',', '،', ';', '؛', '،')]
                boundary = max(candidates)
                if boundary < 250:
                    boundary = 650
                chunks.append(sentence[:boundary].strip())
                sentence = sentence[boundary:].strip()
            if sentence:
                chunks.append(sentence)
    return chunks


def natural_pause(sentence, speaker):
    """Add measured silence after each synthesized phrase."""
    end = sentence.rstrip()
    if end.endswith(('?', '!', '؟')):
        return 200
    if end.endswith(('।', '.')):
       return 150
    if end.endswith((',', '،', ';', '؛', ':')):
        return 80
    return 50


def format_rate(value):
    return f'{clamp(value, -50, 50):+d}%'


def format_pitch(value):
    return f'{clamp(value, -30, 30):+d}Hz'


def format_volume(value):
    return f'{clamp(value, -50, 50):+d}%'


async def create_segment(text, voice, rate, pitch, volume, filepath):
    """Retry transient empty audio; use neutral controls as a final fallback."""
    attempts = [(rate, pitch, volume), (rate, pitch, volume), ('+0%', '+0Hz', '+0%')]
    for attempt, (r, p, v) in enumerate(attempts, start=1):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            app.logger.info('TTS segment attempt=%s voice=%s rate=%s pitch=%s volume=%s chars=%s',
                            attempt, voice, r, p, v, len(text))
            await edge_tts.Communicate(text=text, voice=voice, rate=r, pitch=p, volume=v).save(filepath)
            if os.path.getsize(filepath) == 0:
                raise NoAudioReceived('Empty audio file')
            if attempt == 3:
                app.logger.warning('TTS succeeded with neutral controls; original pitch/speed not preserved')
            return
        except NoAudioReceived:
            app.logger.warning('NoAudioReceived on attempt %s/3 voice=%s', attempt, voice)
            if attempt == 3:
                raise
            await asyncio.sleep(attempt)


def speaker_from_context(context):
    # Prefer a role next to a speech verb, not a random earlier mention.
    matches = list(ROLE_PATTERN.finditer(context))
    if not matches:
        return None
    for match in reversed(matches):
        after = context[match.end():]
        if len(after) <= 65 and SPEECH_PATTERN.search(after):
            return match.group(), ROLE_GENDERS[match.group()]
    return None


def story_chunks(text):
    """Extract quoted dialogue; unquoted portions stay narrator text.
    Supports 'पापा ने कहा, "..."' and '"...", पापा ने कहा' forms.
    """
    result = []
    cursor = 0
    matches = list(QUOTES.finditer(text))
    for index, match in enumerate(matches):
        before = text[cursor:match.start()]
        after = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        # Determine speaker using nearest speech attribution, before or after quote.
        # Keep full narration text even when attribution is detected.
        prefix = before[-130:]
        speaker = speaker_from_context(prefix)
        if speaker is None:
            suffix = after[:90]
            speaker = speaker_from_context(suffix)
        if before.strip():
            result.append({'text': before.strip(), 'gender': 'female', 'emotion': detect_emotion(before), 'speaker': 'narrator'})
        dialogue = match.group(1).strip()
        if dialogue:
            gender = speaker[1] if speaker else 'female'
            role = speaker[0] if speaker else 'narrator'
            # Explicit attribution emotion takes priority over the dialogue's keyword score.
            hint = prefix if speaker_from_context(prefix) else (after[:90] if speaker else '')
            hinted_emotion = detect_emotion(hint)
            emotion = hinted_emotion if hinted_emotion != 'normal' else detect_emotion(dialogue)
            result.append({'text': dialogue, 'gender': gender, 'emotion': emotion, 'speaker': role})
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        result.append({'text': tail.strip(), 'gender': 'female', 'emotion': detect_emotion(tail), 'speaker': 'narrator'})
    # No quote marks: support explicit 'पापा: ...' lines.
    if not matches:
        result = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^([^:：]{1,25})\s*[:：]\s*(.+)$', line)
            if m and m.group(1).strip() in ROLE_GENDERS:
                role = m.group(1).strip()
                result.append({'text': m.group(2).strip(), 'gender': ROLE_GENDERS[role], 'emotion': detect_emotion(m.group(2)), 'speaker': role})
            else:
                result.append({'text': line, 'gender': 'female', 'emotion': detect_emotion(line), 'speaker': 'narrator'})
    return result


async def synthesize_parts(parts, job_id, base_speed=0, base_pitch=0, default_style=None):
    final_audio = AudioSegment.empty()
    segment_files = []
    try:
        index = 0
        for part in parts:
            for sentence in split_sentences(part['text']):
                if not sentence.strip():
                    continue
                emotion = part['emotion']
                settings = EMOTIONS.get(emotion, EMOTIONS['normal'])
                # Subtle role variation; base Hindi voices remain Swara/Madhur.
                style_key = part.get('style') or ROLE_STYLES.get(part.get('speaker')) or default_style or (part['gender'] + '1')
                gender, style_rate, style_pitch = VOICE_STYLES.get(style_key, VOICE_STYLES[part['gender'] + '1'])
                # Keep gender consistent with explicitly detected character.
                if gender != part['gender']:
                    gender, style_rate, style_pitch = VOICE_STYLES[part['gender'] + '1']
                filepath = os.path.join(AUDIO_FOLDER, f'{job_id}_{index}.mp3')
                segment_files.append(filepath)
                await create_segment(sentence, VOICES[gender],
                                     format_rate(clamp(base_speed + settings['rate'] + style_rate + part.get('speed_offset', 0), -50, 50)),
                                     format_pitch(clamp(base_pitch + settings['pitch'] + style_pitch + part.get('pitch_offset', 0), -30, 30)),
                                     format_volume(settings['volume']), filepath)
                final_audio += AudioSegment.from_file(filepath, format='mp3')
                final_audio += AudioSegment.silent(duration=natural_pause(sentence, part.get('speaker')))
                index += 1
        if index == 0:
            raise ValueError('No speakable text found')
        output = os.path.join(AUDIO_FOLDER, f'{job_id}.mp3')
        final_audio.export(output, format='mp3', bitrate='128k')
        return output
    finally:
        for path in segment_files:
            try:
                os.remove(path)
            except OSError:
                pass


@app.route('/', methods=['GET'])
def home():
    return jsonify({'success': True, 'message': 'Text to Voice API with Auto Emotion and Story Voice is running',
                    'voices': list(VOICES), 'speeds': list(SPEEDS), 'pitches': list(PITCHES),
                    'emotions': ['auto', 'normal', 'happy', 'sad', 'angry', 'fear', 'excited'],
                    'story_endpoint': '/story-tts'})


@app.route('/tts', methods=['POST'])
def text_to_speech():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'JSON data is required'}), 400
    text = str(data.get('text', '')).strip()
    voice_type = str(data.get('voice', 'female')).strip().lower()
    speed_type = str(data.get('speed', 'normal')).strip().lower()
    pitch_type = str(data.get('pitch', 'normal')).strip().lower()
    emotion_type = str(data.get('emotion', 'auto')).strip().lower()
    style = str(data.get('voice_style', voice_type + '1')).strip().lower()
    if style not in VOICE_STYLES or VOICE_STYLES[style][0] != voice_type:
        return jsonify({'success': False, 'error': 'Invalid voice style'}), 400
    if not text:
        return jsonify({'success': False, 'error': 'Text is required'}), 400
    if len(text) > MAX_CHARACTERS:
        return jsonify({'success': False, 'error': 'Maximum 10000 characters allowed'}), 400
    if voice_type not in VOICES:
        return jsonify({'success': False, 'error': 'Invalid voice'}), 400
    if speed_type not in SPEEDS:
        return jsonify({'success': False, 'error': 'Invalid speed'}), 400
    if pitch_type not in PITCHES:
        return jsonify({'success': False, 'error': 'Invalid pitch'}), 400
    if emotion_type not in ['auto', 'normal', 'happy', 'sad', 'angry', 'fear', 'excited']:
        return jsonify({'success': False, 'error': 'Invalid emotion'}), 400
    parts = [{'text': sentence, 'gender': voice_type,
              'emotion': detect_emotion(sentence) if emotion_type == 'auto' else emotion_type,
              'speaker': 'narrator'} for sentence in split_sentences(text)]
    try:
        output = asyncio.run(synthesize_parts(parts, uuid.uuid4().hex, SPEEDS[speed_type], PITCHES[pitch_type], style))
        return send_file(output, mimetype='audio/mpeg', as_attachment=False, download_name='voice.mp3')
    except Exception:
        app.logger.exception('TTS generation failed')
        return jsonify({'success': False, 'error': 'Voice generation failed'}), 500


@app.route('/story-tts', methods=['POST'])
def story_to_speech():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': 'JSON data is required'}), 400
    text = str(data.get('text', '')).strip()
    if not text:
        return jsonify({'success': False, 'error': 'Text is required'}), 400
    if len(text) > MAX_CHARACTERS:
        return jsonify({'success': False, 'error': 'Maximum 10000 characters allowed'}), 400
    try:
        parts = story_chunks(text)
        narrator_style = str(data.get('narrator_style', 'female1')).strip().lower()
        if narrator_style not in VOICE_STYLES:
            return jsonify({'success': False, 'error': 'Invalid narrator style'}), 400
        for part in parts:
            if part.get('speaker') == 'narrator':
                part['style'] = narrator_style
                part['gender'] = VOICE_STYLES[narrator_style][0]
        manual = data.get('story_manual', False)
        if not isinstance(manual, bool):
            return jsonify({'success': False, 'error': 'Invalid story_manual'}), 400
        role_settings = data.get('role_settings', {})
        if not isinstance(role_settings, dict):
            return jsonify({'success': False, 'error': 'Invalid role_settings'}), 400
        if manual:
            for part in parts:
                role = ROLE_ALIASES.get(part.get('speaker'), part.get('speaker'))
                if role not in STORY_ROLES:
                    continue
                setting = role_settings.get(role, {})
                if not isinstance(setting, dict):
                    return jsonify({'success': False, 'error': 'Invalid character setting'}), 400
                try:
                    rate = int(setting.get('speed', 0))
                    tone = int(setting.get('pitch', 0))
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'error': 'Pitch and speed must be numbers'}), 400
                if not (-30 <= rate <= 30 and -20 <= tone <= 20):
                    return jsonify({'success': False, 'error': 'Pitch or speed out of range'}), 400
                part['speed_offset'] = rate
                part['pitch_offset'] = tone
        output = asyncio.run(synthesize_parts(parts, uuid.uuid4().hex))
        return send_file(output, mimetype='audio/mpeg', as_attachment=False, download_name='story-voice.mp3')
    except Exception:
        app.logger.exception('Story voice generation failed')
        return jsonify({'success': False, 'error': 'Story voice generation failed'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
