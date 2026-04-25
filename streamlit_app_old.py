import streamlit as st
import requests
import time
import json
import os
import tempfile
from datetime import datetime
from fpdf import FPDF

def check_backend_running():
    try:
        requests.get("http://127.0.0.1:5000/", timeout=2)
        return True
    except requests.exceptions.ConnectionError:
        return False

st.set_page_config(page_title="NotesAI - Smart Video Summarization", layout="wide", initial_sidebar_state="expanded")

# --- CSS STYLING ---
st.markdown("""
<style>
.block-container {
    max-width: 1500px !important;
    margin: 0 auto !important;
    width: 95% !important;
}
.notes-container {
    max-width: 1500px;
    margin: 0 auto;
    width: 95%;
}
.document-block {
    background: #ffffff;
    padding: 50px;
    border-radius: 20px;
    margin-bottom: 40px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    border: 1px solid #eaeaea;
}
.document-block h3 {
    color: #111111;
    margin-top: 0;
    font-size: 32px;
    font-weight: 800;
    padding-bottom: 20px;
    border-bottom: 2px solid #f0f0f0;
    margin-bottom: 30px;
}
.document-block p {
    color: #333333;
    font-size: 20px;
    line-height: 1.9;
    margin-bottom: 20px;
}
.document-block .bullet-point {
    color: #333333;
    font-size: 20px;
    line-height: 1.9;
    margin-bottom: 20px;
    display: flex;
    padding-left: 20px;
}
.document-block .bullet-icon {
    color: #6c5ce7;
    margin-right: 15px;
    font-weight: bold;
}
.stat-box {
    background-color: #2d3436;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    border: 1px solid #636e72;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
.stat-value {
    font-size: 28px;
    font-weight: bold;
    color: #00cec9;
}
.stat-label {
    font-size: 13px;
    color: #b2bec3;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 5px;
}
.lib-card {
    background: #2d3436;
    padding: 20px;
    border-radius: 12px;
    border-left: 4px solid #6c5ce7;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

# --- LIBRARY HELPER FUNCTIONS ---
LIBRARY_FILE = "library.json"

def load_library():
    if os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_to_library(title, content_dict):
    lib = load_library()
    entry = {
        "id": str(time.time()),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title,
        "content": content_dict
    }
    lib.append(entry)
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=4)

def delete_from_library(entry_id):
    lib = load_library()
    lib = [e for e in lib if e["id"] != entry_id]
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=4)

def generate_pdf(text_content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Using latin-1 replacement to avoid encoding errors with standard fonts
    encoded_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=encoded_text)
    # create temporary file and release lock immediately for Windows compatibility
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_name = temp_pdf.name
    temp_pdf.close()
    
    try:
        pdf.output(temp_name)
        with open(temp_name, "rb") as f:
            pdf_bytes = f.read()
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)
            
    return pdf_bytes

# --- SIDEBAR ---
with st.sidebar:
    st.header("✨ Features")
    st.markdown("""
    - ✔ **YouTube Lecture Summarization**
    - ✔ **Uploaded Video Summarization**
    - ✔ **AI Note Extraction**
    - ✔ **PDF & TXT Exports**
    - ✔ **Notes Library Persistence**
    """)
    st.divider()
    st.caption("NotesAI © 2026 | Smart Summarization")

st.title("🧠 NotesAI")
st.markdown("Convert your lecture videos into structured, summarized notes instantly.")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📺 YouTube Link", "📁 Upload Video", "📚 My Notes Library"])

def render_notes(data, processing_time=0.0, is_library_view=False):
    if "error" in data:
        st.error(data["error"])
        return
        
    if not is_library_view:
        st.success("✨ Notes generated successfully!")
        
    overview = data.get("overview", [])
    
    # Check if we have the new explicit Gemini format
    if "key_points" in data and "examples" in data and "conclusion" in data:
        key_points = data.get("key_points", [])
        examples = data.get("examples", [])
        important_concepts = data.get("concepts", [])
        conclusion = data.get("conclusion", [])
        definition = []
        overview_rem = overview
    else:
        # Fallback to old LSTM splitting logic
        points = data.get("points", [])
        concepts = data.get("concepts", [])
        
        definition = overview[:1] if overview else []
        overview_rem = overview[1:] if len(overview) > 1 else []
        
        mid_pts = len(points) // 2
        key_points = points[:mid_pts]
        examples = points[mid_pts:]
        
        conc_len = len(concepts)
        important_concepts = concepts[:max(1, conc_len - 2)]
        conclusion = concepts[max(1, conc_len - 2):]
    
    expand_notes = st.toggle("Expand Notes to Full Width Reading Mode", value=True, key=f"tgl_{time.time()}")
    
    html = f'<div class="notes-container">'
    
    if definition or overview_rem:
        content = []
        if definition:
            content.append(f'<p><b>Definition:</b> {definition[0]}</p>')
        for p in overview_rem:
            content.append(f'<div class="bullet-point"><span class="bullet-icon">•</span><span>{p}</span></div>')
        html += f'''<div class="document-block">
            <h3>📖 Overview & Definition</h3>
            {''.join(content)}
        </div>'''
        
    if key_points:
        html += f'''<div class="document-block">
            <h3>💡 Key Points</h3>
            {''.join([f'<div class="bullet-point"><span class="bullet-icon">•</span><span>{p}</span></div>' for p in key_points])}
        </div>'''
        
    if examples:
        html += f'''<div class="document-block">
            <h3>🛠️ Examples</h3>
            {''.join([f'<div class="bullet-point"><span class="bullet-icon">•</span><span>{p}</span></div>' for p in examples])}
        </div>'''
        
    if important_concepts:
        html += f'''<div class="document-block">
            <h3>🧠 Important Concepts</h3>
            {''.join([f'<div class="bullet-point"><span class="bullet-icon">•</span><span>{p}</span></div>' for p in important_concepts])}
        </div>'''
        
    if conclusion:
        html += f'''<div class="document-block">
            <h3>🎯 Conclusion</h3>
            {''.join([f'<div class="bullet-point"><span class="bullet-icon">•</span><span>{p}</span></div>' for p in conclusion])}
        </div>'''
        
    html += '</div>'
    
    st.markdown(html, unsafe_allow_html=True)
    
    if not is_library_view:
        st.write("---")
        total_extracted = len(overview) + len(points) + len(concepts)
        estimated_transcribed = total_extracted * 6
        st.subheader("📊 Processing Statistics")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-value">~{estimated_transcribed}</div><div class="stat-label">Sentences Transcribed</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-value">{total_extracted}</div><div class="stat-label">Notes Extracted</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-box"><div class="stat-value">{processing_time:.1f}s</div><div class="stat-label">Processing Time</div></div>', unsafe_allow_html=True)
        
        st.write("")
        
        # Save & Download
        text_content = "NOTES AI - GENERATED NOTES\n" + "="*30 + "\n\n"
        if definition: text_content += f"DEFINITION:\n- {definition[0]}\n\n"
        text_content += "OVERVIEW:\n" + "\n".join([f"- {p}" for p in overview_rem]) + "\n\n"
        text_content += "KEY POINTS:\n" + "\n".join([f"- {p}" for p in key_points]) + "\n\n"
        text_content += "EXAMPLES:\n" + "\n".join([f"- {p}" for p in examples]) + "\n\n"
        text_content += "CONCEPTS:\n" + "\n".join([f"- {p}" for p in important_concepts]) + "\n\n"
        text_content += "CONCLUSION:\n" + "\n".join([f"- {p}" for p in conclusion]) + "\n"
        
        pdf_bytes = generate_pdf(text_content)
        
        sc1, sc2, sc3 = st.columns([1, 1, 1])
        with sc1:
            st.download_button("📥 Download as TXT", text_content, file_name="notes_summary.txt", use_container_width=True)
        with sc2:
            st.download_button("📄 Download as PDF", pdf_bytes, file_name="notes_summary.pdf", mime="application/pdf", use_container_width=True)
        with sc3:
            if st.button("💾 Save to Notes Library", use_container_width=True):
                save_to_library("Generated Notes", data)
                st.toast("Notes saved to library! ✅", icon="💾")

# --- TAB 1: YOUTUBE ---
with tab1:
    col1, col2 = st.columns([4, 1])
    with col1:
        youtube_url = st.text_input("Enter YouTube Video URL:", placeholder="https://youtube.com/watch?v=...", key="yt_input")
    with col2:
        st.write("")
        st.write("")
        if st.button("Use Demo 🎬", use_container_width=True):
            # A great academic demo video
            youtube_url = "https://www.youtube.com/watch?v=aircAruvnKk" 
            st.info(f"Loaded demo link: {youtube_url}")
            
    if st.button("Generate Notes from URL", type="primary", use_container_width=True):
        if not check_backend_running():
            st.error("Backend server not running. Start Flask server.")
        elif youtube_url:
            with st.status("Processing YouTube Video...", expanded=True) as status:
                start_time = time.time()
                try:
                    status.update(label="Extracting Audio and Transcribing...", state="running")
                    response = requests.post(
                        "http://127.0.0.1:5000/generate",
                        json={"text": youtube_url}
                    )
                    end_time = time.time()
                    
                    print(f"Backend Response Code: {response.status_code}")
                    if response.status_code == 200:
                        try:
                            res_data = response.json()
                            print(f"Backend Response JSON: {res_data}")
                            if res_data.get("success"):
                                status.update(label="Structuring Notes...", state="running")
                                time.sleep(0.5) # Simulate structuring phase
                                status.update(label="Complete!", state="complete", expanded=False)
                                render_notes(res_data.get("summary", {}), end_time - start_time)
                            else:
                                error_msg = res_data.get("error", "Notes generation failed.")
                                status.update(label=f"Error: {error_msg}", state="error")
                                st.error(f"Error Details: {error_msg}")
                        except Exception as e:
                            print(f"JSON Parse Error: {e}")
                            status.update(label="Frontend Parsing Error", state="error")
                            st.error(f"Error parsing server response: {response.text}")
                    else:
                        try:
                            res_data = response.json()
                            print(f"Backend Error JSON: {res_data}")
                            error_msg = res_data.get("error", response.text)
                            if res_data.get("details"):
                                st.error(f"Backend Details:\n{res_data.get('details')}")
                        except Exception:
                            error_msg = response.text
                        status.update(label=f"Error: {error_msg}", state="error")
                        st.error(f"Server Error Details: {error_msg}")
                except requests.exceptions.ConnectionError:
                    status.update(label="Connection Error", state="error")
                    st.error("Backend server not running. Start Flask server.")
                except Exception as e:
                    status.update(label="Unknown Error", state="error")
                    st.error(f"An unexpected error occurred: {e}")
        else:
            st.warning("Please enter a valid YouTube URL first.")

# --- TAB 2: UPLOAD VIDEO ---
with tab2:
    uploaded_file = st.file_uploader("Upload a video file", type=["mp4", "webm", "mov", "avi"])
    
    if st.button("Generate Notes from Video", type="primary", use_container_width=True):
        if not check_backend_running():
            st.error("Backend server not running. Start Flask server.")
        elif uploaded_file is not None:
            with st.status("Processing Uploaded Video...", expanded=True) as status:
                start_time = time.time()
                try:
                    status.update(label="Chunking and Transcribing Audio...", state="running")
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    response = requests.post(
                        "http://127.0.0.1:5000/upload_video",
                        files=files
                    )
                    end_time = time.time()
                    
                    print(f"Backend Response Code: {response.status_code}")
                    if response.status_code == 200:
                        try:
                            res_data = response.json()
                            print(f"Backend Response JSON: {res_data}")
                            if res_data.get("success"):
                                status.update(label="Structuring Academic Notes...", state="running")
                                time.sleep(0.5)
                                status.update(label="Complete!", state="complete", expanded=False)
                                render_notes(res_data.get("summary", {}), end_time - start_time)
                            else:
                                error_msg = res_data.get("error", "Notes generation failed.")
                                status.update(label=f"Error: {error_msg}", state="error")
                                st.error(f"Error Details: {error_msg}")
                        except Exception as e:
                            print(f"JSON Parse Error: {e}")
                            status.update(label="Frontend Parsing Error", state="error")
                            st.error(f"Error parsing server response: {response.text}")
                    else:
                        try:
                            res_data = response.json()
                            print(f"Backend Error JSON: {res_data}")
                            error_msg = res_data.get("error", "Backend route error")
                            if res_data.get("details"):
                                st.error(f"Backend Details:\n{res_data.get('details')}")
                        except Exception:
                            error_msg = "Backend route error"
                        status.update(label=f"Error: {error_msg}", state="error")
                        st.error(f"Server Error Details: {error_msg}")
                except requests.exceptions.ConnectionError:
                    status.update(label="Connection Error", state="error")
                    st.error("Backend server not running. Start Flask server.")
                except Exception as e:
                    status.update(label="Unknown Error", state="error")
                    st.error(f"An unexpected error occurred: {e}")
        else:
            st.warning("Please upload a video file first.")

# --- TAB 3: MY LIBRARY ---
with tab3:
    st.subheader("📚 Saved Notes Library")
    lib_data = load_library()
    if not lib_data:
        st.info("Your library is empty. Save some notes first!")
    else:
        for idx, entry in enumerate(reversed(lib_data)):
            with st.container():
                st.markdown(f'''
                <div class="lib-card">
                    <h4>{entry["title"]}</h4>
                    <small style="color: #b2bec3;">Saved on: {entry["date"]}</small>
                </div>
                ''', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 4])
                with c1:
                    if st.button("🗑️ Delete", key=f"del_{entry['id']}_{idx}"):
                        delete_from_library(entry["id"])
                        st.rerun()
                with c2:
                    with st.expander("👁️ View Notes"):
                        render_notes(entry["content"], is_library_view=True)
            st.write("")
