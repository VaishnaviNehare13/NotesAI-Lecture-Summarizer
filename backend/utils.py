import os
import re
import pickle
import nltk
from nltk.tokenize import sent_tokenize
import google.generativeai as genai
from dotenv import load_dotenv
import json

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')

print("Loading models...")

whisper_model = None
if WHISPER_AVAILABLE:
    try:
        whisper_model = whisper.load_model("base")
    except Exception as e:
        print(f"Error loading whisper model: {e}")

if TORCH_AVAILABLE:
    class SimpleModel(nn.Module):
        def __init__(self, input_size=500):
            super().__init__()
            self.fc = nn.Linear(input_size, 1)
            self.sigmoid = nn.Sigmoid()

        def forward(self, x):
            return self.sigmoid(self.fc(x))
else:
    SimpleModel = None

try:
    # We must construct an absolute path to the vectorizer because this script 
    # will run from the main directory via python backend/api.py
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vectorizer_path = os.path.join(base_dir, "vectorizer.pkl")
    with open(vectorizer_path, "rb") as f:
        vectorizer = pickle.load(f)
except Exception:
    vectorizer = None

lstm_model = None
if TORCH_AVAILABLE and SimpleModel:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:
        lstm_model = SimpleModel(input_size=500).to(device)
        lstm_path = os.path.join(base_dir, "lstm_model.pth")
        lstm_model.load_state_dict(torch.load(lstm_path, map_location=device))
        lstm_model.eval()
    except Exception as e:
        print(f"Error loading LSTM model: {e}")

def clean_transcript(text):
    """Robust transcript cleaning to remove hallucinations and filler"""
    if not text:
        return ""
    # Remove common Whisper hallucinations
    hallucinations = [
        "thank you for watching", "thanks for watching", "please subscribe",
        "subscribe to the channel", "subscribe to my channel",
        "amara.org", "subtitle", "by amara"
    ]
    text_lower = text.lower()
    for h in hallucinations:
        if h in text_lower:
            text = re.compile(re.escape(h), re.IGNORECASE).sub("", text)
    
    # Remove multiple repeated words (e.g. "so so so so")
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text, flags=re.IGNORECASE)
    return text.strip()

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s.]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_notes_with_lstm(transcription):
    try:
        transcription = clean_transcript(transcription)
        cleaned_txt = clean_text(transcription)
        sentences = sent_tokenize(cleaned_txt)
        
        # Fallback for unpunctuated transcripts (e.g., raw YouTube captions)
        if len(sentences) < 10 and len(cleaned_txt.split()) > 50:
            words = cleaned_txt.split()
            chunk_size = 20
            sentences = [" ".join(words[i:i+chunk_size]) + "." for i in range(0, len(words), chunk_size)]
        
        # Remove very short fragments and properly format sentences
        sentences = [s.strip().capitalize() for s in sentences if len(s.split()) > 3]
        total_sentences = len(sentences)
        
        if total_sentences == 0:
            return {"error": "No speech detected"}
            
        # Extract meaningful concepts using basic term frequency and bigrams
        import re
        from collections import Counter
        from nltk.corpus import stopwords
        try:
            stop_words = set(stopwords.words('english'))
        except:
            import nltk
            nltk.download('stopwords', quiet=True)
            stop_words = set(stopwords.words('english'))
            
        custom_stops = {"means", "saying", "thing", "okay", "basically", "today", "example", "something", "really", "going", "know", "think", "make", "people", "would", "could", "should", "actually", "probably", "might", "always", "never"}
        stop_words = stop_words.union(custom_stops)
        
        words = re.findall(r'\b[a-z]{4,}\b', cleaned_txt.lower())
        meaningful_words = [w for w in words if w not in stop_words]
        
        # Add bigrams (2-word phrases)
        bigrams = [f"{meaningful_words[i]} {meaningful_words[i+1]}" for i in range(len(meaningful_words)-1)]
        
        # Combine unigrams and bigrams, weigh bigrams slightly higher if they repeat
        all_terms = meaningful_words + bigrams
        common_terms = [word for word, count in Counter(all_terms).most_common(12) if count > 1 or len(word.split()) > 1]
        
        # Filter overlapping unigrams if the bigram is already present
        final_terms = []
        for term in common_terms:
            if not any(term in ft and term != ft for ft in final_terms):
                final_terms.append(term)
            if len(final_terms) == 5:
                break
                
        extracted_concepts = [f"{term.title()}" for term in final_terms]
            
        if lstm_model is None or vectorizer is None:
            top_sentences = sentences[:35]
        else:
            try:
                tfidf_matrix = vectorizer.transform(sentences).toarray()
                tensors = torch.tensor(tfidf_matrix, dtype=torch.float32).to(device)
                
                if len(tensors) == 0:
                    return {"error": "No text could be vectorized properly."}
                    
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
            except Exception as ml_e:
                print(f"ML Processing error, falling back: {ml_e}")
                top_sentences = sentences[:35]
            
        # Guarantee minimum numbers if we have sentences
        n_sent = len(top_sentences)
        if n_sent < 4:
            return {
                "summary": " ".join(top_sentences),
                "key_learnings": [],
                "important_concepts": extracted_concepts[:5],
                "key_points": [],
                "conclusion": ""
            }
            
        # Structure dynamically based on length
        overview_end = min(8, max(1, n_sent // 3))
        points_end = min(20, max(overview_end + 1, int(n_sent * 0.7)))
        
        overview = top_sentences[:overview_end]
        points = top_sentences[overview_end:points_end]
        
        # Dedup extracted sentences
        unique_points = []
        for p in points:
            if p not in unique_points and p not in overview:
                unique_points.append(p)
        
        return {
            "summary": " ".join(overview),
            "key_learnings": unique_points[:4],
            "important_concepts": extracted_concepts[:5],
            "key_points": unique_points[4:8] if len(unique_points) > 4 else [],
            "conclusion": ""
        }
    except Exception as e:
        return {"error": str(e)}

def generate_notes_from_text(transcription):
    if not GEMINI_API_KEY:
        print("[DEBUG] No GEMINI_API_KEY found, falling back to LSTM model.")
        return generate_notes_with_lstm(transcription)
        
    try:
        print("[DEBUG] Prompting Gemini API...")
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = """
        Convert this lecture transcript into concise academic study notes.
        Remove filler words, fix grammar, and summarize the lecture content.
        Extract concise bullet points. Avoid transcript dumping. Limit each array to 5-7 bullets of readable length.
        Generate academically formatted notes.
        
        CRITICAL: For "important_concepts", extract ONLY domain-specific technical concepts or noun phrases relevant to the lecture topic (e.g., "Mutual Exclusion", "Deadlock", "Resource Allocation Graph"). Do NOT extract conversational words, verbs, or weak phrases like "means", "saying", "okay", or "example". Rank concepts by relevance, not raw frequency. Prefer noun phrases over single common words.

        Return structured JSON with EXACTLY this format:
        {
          "summary": "overall summary string",
          "key_learnings": ["bullet 1", "bullet 2"],
          "important_concepts": ["technical concept 1", "technical concept 2"],
          "key_points": ["bullet 1", "bullet 2"],
          "conclusion": "overall conclusion string"
        }
        Respond ONLY with valid JSON. Do not include markdown code blocks like ```json ... ```. Just the raw JSON.
        
        Transcript:
        """ + transcription
        
        response = model.generate_content(prompt)
        return _parse_gemini_json_response(response.text.strip())
        
    except Exception as e:
        print(f"[DEBUG] Gemini generation failed: {e}. Falling back to LSTM.")
        return generate_notes_with_lstm(transcription)

def _parse_gemini_json_response(response_text):
    try:
        # Clean potential markdown formatting
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        print(f"[DEBUG] Raw LLM response before parse:\n{response_text}")
        json_data = json.loads(response_text.strip())
        print(f"[DEBUG] Parsed LLM JSON:\n{json_data}")
        
        # Parse JSON response and map each section into corresponding frontend cards
        summary = json_data.get("summary", "")
        key_learnings = json_data.get("key_learnings", [])
        important_concepts = json_data.get("important_concepts", [])
        key_points = json_data.get("key_points", [])
        conclusion = json_data.get("conclusion", "")
        
        # Fallback if lists are returned as strings
        if isinstance(key_learnings, str): key_learnings = [key_learnings]
        if isinstance(important_concepts, str): important_concepts = [important_concepts]
        if isinstance(key_points, str): key_points = [key_points]
        if isinstance(summary, list): summary = " ".join(summary)
        if isinstance(conclusion, list): conclusion = " ".join(conclusion)
        
        # Fallback if empty
        if not summary: summary = "No lecture summary could be extracted."
        if not key_learnings: key_learnings = ["No key learnings detected."]
        if not important_concepts: important_concepts = ["No important concepts identified."]
        if not key_points: key_points = ["No key points detected."]
                
        print("[DEBUG] Gemini generation successful.")
        return {
            "summary": summary,
            "key_learnings": key_learnings[:7],
            "important_concepts": important_concepts[:7],
            "key_points": key_points[:7],
            "conclusion": conclusion
        }
    except Exception as e:
        return {"error": f"Failed to parse AI response: {e}"}

def generate_notes_from_file(file_path):
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key is required for video/audio extraction."}
        
    try:
        print(f"[DEBUG] Uploading file to Gemini: {file_path}")
        uploaded_file = genai.upload_file(path=file_path)
        
        import time
        if hasattr(uploaded_file, 'state'):
            while uploaded_file.state.name == 'PROCESSING':
                print('.', end='', flush=True)
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)
            if uploaded_file.state.name == 'FAILED':
                raise Exception("Gemini failed to process the media file.")
                
        print("\n[DEBUG] File ready. Prompting Gemini API...")
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = """
        Analyze this audio/video.
        Convert the spoken lecture content into concise academic study notes.
        Remove filler words, fix grammar, and summarize the lecture content.
        Extract concise bullet points. Avoid transcript dumping. Limit each array to 5-7 bullets of readable length.
        Generate academically formatted notes.
        
        CRITICAL: For "important_concepts", extract ONLY domain-specific technical concepts or noun phrases relevant to the lecture topic (e.g., "Mutual Exclusion", "Deadlock", "Resource Allocation Graph"). Do NOT extract conversational words, verbs, or weak phrases like "means", "saying", "okay", or "example". Rank concepts by relevance, not raw frequency. Prefer noun phrases over single common words.

        Return structured JSON with EXACTLY this format:
        {
          "summary": "overall summary string",
          "key_learnings": ["bullet 1", "bullet 2"],
          "important_concepts": ["technical concept 1", "technical concept 2"],
          "key_points": ["bullet 1", "bullet 2"],
          "conclusion": "overall conclusion string"
        }
        Respond ONLY with valid JSON. Do not include markdown code blocks like ```json ... ```. Just the raw JSON.
        """
        
        response = model.generate_content([prompt, uploaded_file])
        
        try:
            genai.delete_file(uploaded_file.name)
        except Exception as cleanup_err:
            print(f"[DEBUG] Failed to cleanup file from Gemini: {cleanup_err}")
            
        return _parse_gemini_json_response(response.text.strip())
        
    except Exception as e:
        print(f"[DEBUG] Gemini file extraction failed: {e}")
        return {"error": f"Failed to extract notes from video/audio: {e}"}

