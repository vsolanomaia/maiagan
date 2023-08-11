from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
import speech_recognition as sr
import time 
import os
from werkzeug.utils import secure_filename
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
import requests

app = Flask(__name__)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize IBM Watson API
authenticator = IAMAuthenticator(os.getenv('IBM_AUTHENTICATOR_KEY'))
assistant = AssistantV2(
    version='2021-06-14',
    authenticator=authenticator
)
assistant.set_service_url(os.getenv('IBM_SERVICE_URL'))

# Create session and get session ID
session = assistant.create_session(
    assistant_id=os.getenv('IBM_ASSISTANT_ID')
).get_result()
session_id = session['session_id']

conversations = []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Procesa el formulario aquí
        # ...
        pass
    return render_template('index.html', chat=conversations)

def transcribe_audio_to_text(filename):
    recognizer = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio = recognizer.record(source) 
    try:
        return recognizer.recognize_google(audio, language="es")
    except Exception as e:
        print(f"Ocurrió un error al transcribir el audio: {e}")

def generate_response(prompt):
    response = assistant.message(
        assistant_id=os.getenv('IBM_ASSISTANT_ID'),
        session_id=session_id,
        input={
            'message_type': 'text',
            'text': prompt
        }
    ).get_result()
    
    url = "https://api.exh.ai/animations/v3/generate_lipsync"

    payload = {
        "text": response['output']['generic'][0]['text'],
        "idle_url": "https://ugc-idle.s3-us-west-2.amazonaws.com/est_26b3c5b67818a51bf899fb8390cf742f.mp4",
        "azure_voice": "es-MX-BeatrizNeural"
    }

    YOUR_API_KEY = os.getenv('EXH_API_KEY')
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {YOUR_API_KEY}"
    }

    response_video = requests.post(url, json=payload, headers=headers)
    response_video.raise_for_status()
    
    filename = f"response_{time.time()}.mp4"
    path_to_response = os.path.join(app.root_path, 'videos', filename)
    
    with open(path_to_response, "wb") as f:
        f.write(response_video.content)
    
    return response['output']['generic'][0]['text'], url_for('serve_video', filename=filename)

@app.route('/audio', methods=['POST'])
def handle_audio():
    audio_file = request.files['audio']
    filename = secure_filename(audio_file.filename)
    audio_file.save(filename)
    text = transcribe_audio_to_text(filename)
    os.remove(filename)
    response, video_path = generate_response(text)
    conversations.append({'question': text, 'response': response})
    return jsonify({'text': response, 'video': video_path})

@app.route('/text', methods=['POST'])
def handle_text():
    data = request.get_json()
    question = data['question']
    response, video_path = generate_response(question)
    conversations.append({'question': question, 'response': response})
    return jsonify({'text': response, 'video': video_path})

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(os.path.join(app.root_path, 'videos'), filename)

if __name__ == "__main__":
    app.run()