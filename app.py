import os
import sys
import tempfile
import yt_dlp
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None
from flask import Flask, request, jsonify, render_template, send_file
import io
from fpdf import FPDF
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

# Import from backend.utils
from backend.utils import whisper_model, generate_notes_from_text, generate_notes_from_audio

# Add local bin directory to PATH for ffmpeg
bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
if bin_dir not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + bin_dir

app = Flask(__name__)
CORS(app)

DB_NAME = "notes.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            summary TEXT,
            key_learnings TEXT,
            important_concepts TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

def whisper_transcribe_from_youtube(url):
    try:
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'extract_flat': False,
            'cookiefile': None
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if WHISPER_AVAILABLE and whisper_model:
                with tempfile.TemporaryDirectory() as tmpdir:
                    audio_opts = {
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
                    with yt_dlp.YoutubeDL(audio_opts) as ydl_audio:
                        ydl_audio.download([url])
                        audio_file = os.path.join(tmpdir, f"{info['id']}.mp3")
                        if os.path.exists(audio_file):
                            result = whisper_model.transcribe(audio_file)
                            return result["text"]
            
            description = info.get('description', '')
            if description and description.strip():
                print("[DEBUG] Using YouTube description as fallback text.")
                return description
    except Exception as e:
        print(f"[ERROR] yt-dlp / fallback failed: {e}")
    return None

def get_text_from_video(url):
    import re
    from youtube_transcript_api import YouTubeTranscriptApi
    
    def extract_video_id(url):
        import urllib.parse as urlparse
        parsed = urlparse.urlparse(url)
        if parsed.hostname == 'youtu.be':
            return parsed.path[1:12]
        if parsed.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed.path == '/watch':
                query = urlparse.parse_qs(parsed.query)
                return query['v'][0][:11] if 'v' in query else None
            elif parsed.path.startswith('/embed/'):
                return parsed.path.split('/')[2][:11]
            elif parsed.path.startswith('/v/'):
                return parsed.path.split('/')[2][:11]
        
        # Regex fallback
        match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
        if match:
            return match.group(1)
        return None
        
    video_id = extract_video_id(url)
    if not video_id:
        print(f"[ERROR] Invalid video ID extracted from: {url}")
        raise Exception("Invalid YouTube URL. Could not extract Video ID.")
        
    print(f"[DEBUG] Extracted Video ID: {video_id}")
        
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try to fetch English, but fallback to any available translated
        try:
            transcript = transcript_list.find_transcript(['en']).fetch()
        except:
            print("[DEBUG] No manual English transcript found. Trying to fetch first available and translate.")
            first_available = list(transcript_list)[0]
            transcript = first_available.translate('en').fetch()
            
        text = " ".join([t['text'] for t in transcript])
        print("[DEBUG] youtube_transcript_api successful.")
        return text
    except Exception as e:
        print(f"[ERROR] youtube_transcript_api failed: {e}")
        print("[DEBUG] Falling back to yt-dlp + whisper audio extraction...")
        
        result = whisper_transcribe_from_youtube(url)
        if not result:
            raise Exception("YouTube extraction failed entirely. Video may be private or unavailable.")
        return result

@app.route("/")
@app.route("/<path:page>")
def serve_pages(page="index.html"):
    if not page.endswith(".html"):
        page += ".html"
    try:
        return render_template(page)
    except:
        return render_template("index.html")

@app.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")

@app.route("/style.css")
def serve_css():
    return app.send_static_file("style.css")

@app.route("/script.js")
def serve_js():
    return app.send_static_file("script.js")

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"})

@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    try:
        data = request.get_json()
        text_content = data.get("text_content", "")
        if not text_content:
            return jsonify({"error": "No text content provided"}), 400
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        encoded_text = text_content.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, txt=encoded_text)
        
        # Output directly to memory
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        
        return send_file(
            io.BytesIO(pdf_bytes), 
            as_attachment=True, 
            download_name="NotesAI_Summary.pdf", 
            mimetype="application/pdf"
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/save_note", methods=["POST"])
def save_note():
    try:
        data = request.get_json()
        if not data or 'title' not in data or 'data' not in data:
            return jsonify({"success": False, "error": "Invalid note payload"}), 400
            
        title = data.get("title", "Untitled Note")
        note_data = data.get("data", {})
        
        summary = note_data.get("topic-overview", [""])[0] if note_data.get("topic-overview") else ""
        key_learnings = json.dumps(note_data.get("key-points", []))
        important_concepts = json.dumps(note_data.get("important-concepts", []))
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notes (title, summary, key_learnings, important_concepts)
            VALUES (?, ?, ?, ?)
        ''', (title, summary, key_learnings, important_concepts))
        
        conn.commit()
        note_id = cursor.lastrowid
        conn.close()
        
        return jsonify({"success": True, "id": note_id})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/library", methods=["GET"])
def get_library():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notes ORDER BY created_at DESC')
        rows = cursor.fetchall()
        
        notes = []
        for r in rows:
            notes.append({
                "id": r["id"],
                "title": r["title"],
                "date": datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%m/%d/%Y") if r["created_at"] else "",
                "data": {
                    "topic-overview": [r["summary"]],
                    "key-points": json.loads(r["key_learnings"]) if r["key_learnings"] else [],
                    "important-concepts": json.loads(r["important_concepts"]) if r["important_concepts"] else []
                }
            })
            
        conn.close()
        return jsonify({"success": True, "notes": notes})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/delete_note/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/delete_all_notes", methods=["DELETE"])
def delete_all_notes():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notes')
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"success": False, "error": "No text/url provided"}), 400
            
        input_text = data.get("text", "")
        print(f"[DEBUG] Received generate request for: {input_text}")
        
        if "youtube.com" in input_text or "youtu.be" in input_text:
            transcription = get_text_from_video(input_text)
            if not transcription:
                raise Exception("No captions found")
        else:
            transcription = input_text
            
        print(f"[DEBUG] Transcript extracted. Length: {len(transcription)}")
        
        result = generate_notes_from_text(transcription)
        if "error" in result:
            raise Exception(result["error"])
            
        print("[DEBUG] Summary generated successfully.")
        return jsonify({"success": True, "summary": result})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "details": traceback.format_exc()
        }), 500

@app.route("/upload_video", methods=["POST"])
def upload_video():
    tmp_path = None
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No selected file"}), 400
            
        print(f"[DEBUG] Received upload video request: {file.filename}")
        
        # Save file explicitly to uploads directory
        os.makedirs("uploads", exist_ok=True)
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        if not filename:
            filename = "uploaded_video.mp4"
        tmp_path = os.path.join("uploads", filename)
        
        file.save(tmp_path)
            
        if not WHISPER_AVAILABLE or whisper_model is None:
            import ffmpeg
            audio_path = os.path.join("uploads", f"audio_{filename}.mp3")
            try:
                print(f"[DEBUG] Extracting audio using ffmpeg-python from {tmp_path}")
                ffmpeg.input(tmp_path).output(audio_path, acodec='libmp3lame', ab='128k').run(quiet=True, overwrite_output=True)
                
                notes_result = generate_notes_from_audio(audio_path)
                
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
                if "error" in notes_result:
                    raise Exception(notes_result["error"])
                    
                print("[DEBUG] Audio summary generated via Gemini.")
                return jsonify({"success": True, "summary": notes_result})
            except Exception as e:
                print(f"FFmpeg or Gemini Audio error: {e}")
                raise e
        else:
            # Transcribe handles chunking naturally with 30s sliding window
            result = whisper_model.transcribe(tmp_path)
            transcription = result.get("text", "")
            
            # Cleanup file after processing
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                tmp_path = None
                
            print(f"[DEBUG] Transcript extracted. Length: {len(transcription)}")
            
            if not transcription.strip():
                raise Exception("No speech detected")
                
            # Generate notes
            notes_result = generate_notes_from_text(transcription)
            if "error" in notes_result:
                raise Exception(notes_result["error"])
                
            print("[DEBUG] Summary generated successfully.")
            return jsonify({"success": True, "summary": notes_result})
        
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "details": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
