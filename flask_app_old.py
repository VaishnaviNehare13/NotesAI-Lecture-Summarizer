import os
import re
import pickle
import tempfile
import whisper
import torch

# Add local bin directory to PATH for ffmpeg
bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
if bin_dir not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + bin_dir

import torch.nn as nn
import nltk
from nltk.tokenize import sent_tokenize
from youtube_transcript_api import YouTubeTranscriptApi
from flask import Flask, request, jsonify, render_template

from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')

# Load Models
print("Loading models...")

try:
    whisper_model = whisper.load_model("base")
except Exception as e:
    print(f"Error loading whisper model: {e}")
    whisper_model = None

class SimpleModel(nn.Module):
    def __init__(self, input_size=500):
        super().__init__()
        self.fc = nn.Linear(input_size, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        return self.sigmoid(self.fc(x))

try:
    with open("vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
except Exception:
    vectorizer = None

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
try:
    lstm_model = SimpleModel(input_size=500).to(device)
    lstm_model.load_state_dict(torch.load("lstm_model.pth", map_location=device))
    lstm_model.eval()
except Exception:
    lstm_model = None

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s.]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def whisper_transcribe_from_youtube(url):
    import tempfile
    import os
    import yt_dlp
    
    if whisper_model is None:
        print("Whisper model not loaded.")
        return None
        
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_file = os.path.join(tmpdir, f"{info['id']}.mp3")
                
                if os.path.exists(audio_file):
                    result = whisper_model.transcribe(audio_file)
                    return result["text"]
    except Exception as e:
        print(f"yt-dlp / whisper error: {e}")
        
    return None

def get_text_from_video(url):
    import re
    from youtube_transcript_api import YouTubeTranscriptApi
    
    def extract_video_id(url):
        match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
        if match:
            return match.group(1)
        return None
        
    video_id = extract_video_id(url)
    if not video_id:
        return None
        
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        text = " ".join([t['text'] for t in transcript])
        return text
    except Exception as e:
        print("Transcript API Error:", e)
        print("Falling back to yt-dlp + whisper...")
        return whisper_transcribe_from_youtube(url)

def generate_notes_from_text(transcription):
    try:
        cleaned_txt = clean_text(transcription)
        sentences = sent_tokenize(cleaned_txt)
        total_sentences = len(sentences)
        
        if total_sentences == 0:
            return {"error": "No valid sentences found."}
            
        if lstm_model is None or vectorizer is None:
            # Fallback if AI models are missing
            top_sentences = sentences[:35]
        else:
            tfidf_matrix = vectorizer.transform(sentences).toarray()
            tensors = torch.tensor(tfidf_matrix, dtype=torch.float32).to(device)
            
            scores = []
            with torch.no_grad():
                for i in range(len(tensors)):
                    tensor_input = tensors[i].unsqueeze(0)
                    try:
                        score = lstm_model(tensor_input.unsqueeze(1))
                    except:
                        score = lstm_model(tensor_input)
                    if isinstance(score, tuple):
                        score = score[0]
                    scores.append(score.item())
                    
            ranked_sentences = sorted(enumerate(sentences), key=lambda x: scores[x[0]], reverse=True)
            top_ranked = ranked_sentences[:35]
            top_ranked.sort(key=lambda x: x[0])
            top_sentences = [sent for idx, sent in top_ranked]
            
        # Structure notes exactly as requested
        overview = top_sentences[:10]
        points = top_sentences[10:25]
        concepts = top_sentences[25:35]
        
        return {
            "overview": overview,
            "points": points,
            "concepts": concepts
        }
    except Exception as e:
        return {"error": str(e)}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "No text/url provided"}), 400
        
    input_text = data.get("text", "")
    
    if "youtube.com" in input_text or "youtu.be" in input_text:
        transcription = get_text_from_video(input_text)
        if not transcription:
            return jsonify({"error": "Error fetching transcript. Is the video accessible?"}), 500
    else:
        transcription = input_text
        
    result = generate_notes_from_text(transcription)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@app.route("/upload_video", methods=["POST"])
def upload_video():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if whisper_model is None:
        return jsonify({"error": "Whisper model is not available."}), 500
        
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
            
        # Transcribe
        result = whisper_model.transcribe(tmp_path)
        transcription = result["text"]
        
        # Cleanup temp file
        os.remove(tmp_path)
        
        if not transcription.strip():
            return jsonify({"error": "Could not extract text from the video."}), 400
            
        # Generate notes
        notes_result = generate_notes_from_text(transcription)
        if "error" in notes_result:
            return jsonify(notes_result), 500
            
        return jsonify(notes_result)
        
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
