// Constants
const THEME_KEY = 'notesgen_theme';
let currentGeneratedNotes = null; // Buffer to hold newest generation
let modalNoteDataTarget = null; // Buffer to hold currently viewed note in modal

function getSavedNotesKey() {
    const userEmail = localStorage.getItem("user");
    if(!userEmail) return 'notesgen_saved_notes_anon';
    return `notesgen_saved_notes_${userEmail}`;
}

// ------ EXACT AUTH FUNCTIONS REQUESTED BY USER ------
function loginUser() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    if (!email || !password) {
        showToast("Please fill all fields", "error");
        return;
    }

    localStorage.setItem("user", email);
    window.location.href = "dashboard.html";
}

function signupUser() {
    const email = document.getElementById("email") ? document.getElementById("email").value : null;
    const password = document.getElementById("password") ? document.getElementById("password").value : null;
    const name = document.getElementById("name") ? document.getElementById("name").value : email.split('@')[0];

    if (!email || !password) {
        showToast("Please fill all fields", "error");
        return;
    }

    localStorage.setItem("user", email);
    localStorage.setItem("password", password);
    localStorage.setItem("user_name", name);

    showToast("Account created successfully", "success");
    setTimeout(() => {
        window.location.href = "login.html";
    }, 1500);
}

function logoutUser() {
    localStorage.removeItem("user");
    window.location.href = "login.html";
}
// ------ END AUTH FUNCTIONS ------

// Check Global state
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    handleRouting();
    attachEventListeners();
    
    // Check initial Dashboard Stats if logged in
    const isDashboard = document.getElementById('dashboard-page');
    const isAccount = document.getElementById('account-page');
    const currentUser = localStorage.getItem("user");
    
    if(isDashboard && currentUser) {
        updateDashboardStats();
    }
    if(isAccount && currentUser) {
        loadAccountData();
    }
});

function handleRouting() {
    const isAuthPage = document.getElementById('auth-page');
    const isDashboard = document.getElementById('dashboard-page');
    const isAccount = document.getElementById('account-page');
    
    // Protect Dashboard & Account
    if ((isDashboard || isAccount) && !localStorage.getItem("user")) {
        window.location.href = "login.html";
    }
    // Redirect Auth if already logged in
    if (isAuthPage && localStorage.getItem("user")) {
        window.location.href = "dashboard.html";
    }
    
    if (isDashboard && localStorage.getItem("user")) {
        const userEmail = localStorage.getItem("user");
        const firstName = userEmail.split('@')[0];
        document.getElementById('welcome-message').textContent = `Welcome back, ${firstName} 🎓`;
        const avatar = document.getElementById('user-avatar');
        if(avatar) avatar.textContent = firstName.charAt(0).toUpperCase();
    }
}

// ------ ACCOUNT SPECIFIC LOGIC ------
function loadAccountData() {
    const email = localStorage.getItem("user") || "email@domain.com";
    let name = localStorage.getItem("user_name") || email.split('@')[0];
    
    const accountName = document.getElementById('account-name');
    const accountEmail = document.getElementById('account-email');
    const accountAvt = document.getElementById('account-avatar');
    
    if(accountName) accountName.textContent = name;
    if(accountEmail) accountEmail.textContent = email;
    if(accountAvt) accountAvt.textContent = name.charAt(0).toUpperCase();

    // Fill edit form
    const editName = document.getElementById('edit-name');
    const editEmail = document.getElementById('edit-email');
    if(editName) editName.value = name;
    if(editEmail) editEmail.value = email;
}

function toggleEditProfile() {
    const view = document.getElementById('profile-view');
    const edit = document.getElementById('profile-edit');
    if(view) view.classList.toggle('hidden');
    if(edit) edit.classList.toggle('hidden');
}

function saveProfile() {
    const newName = document.getElementById('edit-name').value;
    const newEmail = document.getElementById('edit-email').value;
    
    if(!newName || !newEmail) return;
    
    localStorage.setItem("user_name", newName);
    localStorage.setItem("user", newEmail);
    
    showToast("Profile updated successfully! ✅", "success");
    loadAccountData();
    toggleEditProfile();
}
// ------ END ACCOUNT LOGIC ------

function attachEventListeners() {
    // Generator Form
    const genForm = document.getElementById('url-form');
    if (genForm) {
        genForm.addEventListener('submit', handleGenerate);
    }

    // Theme Toggle
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const currentTheme = document.body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', newTheme);
            localStorage.setItem(THEME_KEY, newTheme);
            updateThemeBtnText(newTheme);
        });
    }

    // Mobile Menu
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    // Modal Close outside click
    const modal = document.getElementById('modal-overlay');
    if(modal) {
        modal.addEventListener('click', (e) => {
            if(e.target === modal) closeModal();
        });
    }   const searchInput = document.getElementById("searchInput");
    if(searchInput) {
        searchInput.addEventListener("input", function() {
            const value = this.value.toLowerCase();
            document.querySelectorAll(".saved-note-card").forEach(card => { // Added block/flex fix safely
                const displayType = card.classList.contains('saved-note-card') ? 'flex' : 'block';
                card.style.display = card.innerText.toLowerCase().includes(value) ? displayType : "none";
            });
        });
    }

}

function initTheme() {
    const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    updateThemeBtnText(savedTheme);
}

function updateThemeBtnText(theme) {
    const btn = document.getElementById('theme-toggle');
    if(btn) {
        btn.innerHTML = theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
    }
}

function logout() {
    localStorage.removeItem(CURRENT_USER_KEY);
    window.location.href = 'login.html';
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if(!toast) return;
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => { toast.className = 'toast'; }, 3000);
}

// Dashboard Navigation
function navigateDashboard(viewId) {
    document.querySelectorAll('.dashboard-home, .generator-view').forEach(el => {
        el.classList.add('hidden');
    });
    const target = document.getElementById(viewId);
    if(target) target.classList.remove('hidden');

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if(link.getAttribute('onclick')?.includes(viewId)) {
            link.classList.add('active');
        }
    });

    // Close mobile sidebar
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
    }

    if(viewId === 'view-mynotes') {
        loadSavedNotes();
    }
    
    if(viewId === 'view-home') {
        updateDashboardStats();
    }
}

// ------ GENERATION LOGIC ------
// ------ GENERATION LOGIC ------
// Handle File Input UI State
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            const placeholder = document.getElementById('upload-placeholder');
            const fileCard = document.getElementById('upload-file-card');
            const wrapper = document.getElementById('upload-wrapper');
            const filenameEl = document.getElementById('upload-filename');
            const filesizeEl = document.getElementById('upload-filesize');
            const videoInput = document.getElementById('videoInput');
            
            if (file) {
                // Clear URL input if a file is selected
                if(videoInput) videoInput.value = '';
                
                filenameEl.innerText = file.name;
                filesizeEl.innerText = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
                
                placeholder.classList.add('hidden');
                fileCard.classList.remove('hidden');
                
                // Style wrapper
                wrapper.style.borderColor = 'var(--accent)';
                wrapper.style.background = 'rgba(5, 150, 105, 0.02)';
            }
        });
    }
});

function clearUpload(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const fileInput = document.getElementById('fileInput');
    fileInput.value = '';
    
    document.getElementById('upload-placeholder').classList.remove('hidden');
    document.getElementById('upload-file-card').classList.add('hidden');
    
    const wrapper = document.getElementById('upload-wrapper');
    wrapper.style.borderColor = 'var(--border-light)';
    wrapper.style.background = 'var(--bg-main)';
}

async function handleGenerate(e) {
    if(e) e.preventDefault();
    const urlInput = document.getElementById("videoInput").value;
    const fileInput = document.getElementById("fileInput").files[0];
    const btn = document.getElementById("generateBtn");

    if (!urlInput.trim() && !fileInput) return;

    btn.innerText = "Generating...";
    btn.disabled = true;

    document.getElementById("topic-overview").innerHTML = "";
    document.getElementById("key-points").innerHTML = "";
    document.getElementById("important-concepts").innerHTML = "";

    // Check connection first
    try {
        const pingRes = await fetch("/ping");
        if (!pingRes.ok) throw new Error("Backend not responding cleanly");
    } catch (e) {
        alert("Server connection failed. Is Flask running on port 5000?");
        btn.innerText = "Generate Smart Notes 🚀";
        btn.disabled = false;
        return;
    }

    // Toggle UI States
    const emptyState = document.getElementById('empty-state');
    const loadingState = document.getElementById('loading-state');
    const resultsSection = document.getElementById('results-section');
    if(emptyState) emptyState.classList.add('hidden');
    if(resultsSection) resultsSection.classList.add('hidden');
    if(loadingState) loadingState.classList.remove('hidden');

    try {
        let data;
        
        if (fileInput) {
            // Setup Progress Bar UI
            const loadingHeader = loadingState.querySelector('#loading-title');
            const loadingText = loadingState.querySelector('#loading-desc');
            const progressContainer = document.getElementById('upload-progress-container');
            const progressBar = document.getElementById('upload-progress-bar');
            
            if(loadingHeader) loadingHeader.innerText = "Uploading Video...";
            if(loadingText) loadingText.innerText = "Transmitting file to backend processing engine.";
            if(progressContainer) {
                progressContainer.classList.remove('hidden');
                progressBar.style.width = '0%';
            }
            
            const formData = new FormData();
            formData.append('file', fileInput);
            
            // Promise wrapper for XHR to track upload progress
            const resData = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open("POST", "/upload_video", true);
                
                xhr.upload.onprogress = function(e) {
                    if (e.lengthComputable) {
                        const percentComplete = (e.loaded / e.total) * 100;
                        if(progressBar) progressBar.style.width = percentComplete + '%';
                        
                        if (percentComplete === 100) {
                            if(loadingHeader) loadingHeader.innerText = "Processing Intelligence...";
                            if(loadingText) loadingText.innerText = "Upload complete. Running ML pipeline to structure the lecture content.";
                        }
                    }
                };
                
                xhr.onload = function() {
                    let parsedJson = null;
                    try {
                        parsedJson = JSON.parse(xhr.responseText);
                    } catch (err) {
                        // ignore
                    }

                    if (xhr.status >= 200 && xhr.status < 300) {
                        if (parsedJson) {
                            resolve(parsedJson);
                        } else {
                            reject(new Error("Server returned invalid JSON."));
                        }
                    } else {
                        if (parsedJson && parsedJson.error) {
                            reject(new Error(parsedJson.error));
                        } else {
                            reject(new Error("Server error during upload: " + xhr.statusText));
                        }
                    }
                };
                
                xhr.onerror = function() {
                    reject(new Error("Network error occurred during upload."));
                };
                
                xhr.send(formData);
            });
            
            data = resData;
            
            // Clean up progress bar
            if(progressContainer) progressContainer.classList.add('hidden');
            
        } else {
            const res = await fetch("/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: urlInput })
            });
            
            try {
                data = await res.json();
            } catch(jsonErr) {
                throw new Error("Server returned invalid JSON. It might have crashed.");
            }
        }

        if (loadingState) loadingState.classList.add('hidden');

        if (!data.success) {
            setTimeout(() => {
                showToast("Error: " + (data.error || "Generation failed"), "error");
            }, 100);
            if(emptyState) emptyState.classList.remove('hidden');
            btn.innerText = "Generate Smart Notes 🚀";
            btn.disabled = false;
            return;
        }

        const summaryData = data.summary;
        
        let topicOverviewHtml = `<li>${summaryData.summary}</li>`;
        if (summaryData.conclusion) {
            topicOverviewHtml += `<li style="margin-top:0.5rem;"><strong>Conclusion:</strong> ${summaryData.conclusion}</li>`;
        }
        document.getElementById("topic-overview").innerHTML = topicOverviewHtml;
        
        let keyPointsCombined = [...(summaryData.key_learnings || []), ...(summaryData.key_points || [])];
        if(keyPointsCombined.length === 0) keyPointsCombined = ["No key learnings detected."];
        document.getElementById("key-points").innerHTML = keyPointsCombined.map(s => `<li>${s}</li>`).join("");
        
        let conceptsList = summaryData.important_concepts || [];
        if(conceptsList.length === 0) conceptsList = ["No important concepts identified."];
        document.getElementById("important-concepts").innerHTML = conceptsList.map(s => `<li>${s}</li>`).join("");

        // Keep local buffering so Save functionality works
        const tags = ['Generated Note', 'AI'];
        currentGeneratedNotes = {
            id: Date.now(),
            title: `Lecture Notes - ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`,
            date: new Date().toLocaleDateString(),
            tags: tags,
            data: {
                'topic-overview': [summaryData.summary, summaryData.conclusion].filter(Boolean),
                'key-points': keyPointsCombined,
                'important-concepts': conceptsList
            }
        };

        if(resultsSection) {
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

    } catch (e) {
        if(loadingState) loadingState.classList.add('hidden');
        if(emptyState) emptyState.classList.remove('hidden');
        setTimeout(() => {
            showToast("Extraction Error: " + e.message, "error");
        }, 100);
    }

    btn.innerText = "Generate Smart Notes 🚀";
    btn.disabled = false;
}

// ------ NOTES MANAGEMENT ------
let savedNotesList = [];

async function saveNotes() {
    if(!currentGeneratedNotes) return;
    
    // Prevent double clicking save
    const btn = document.getElementById('save-btn');
    if(btn) btn.disabled = true;

    try {
        const res = await fetch("/save_note", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentGeneratedNotes)
        });
        
        const data = await res.json();
        if(data.success) {
            showToast("Notes saved successfully ✅");
            await loadSavedNotes(); // Refresh global list
        } else {
            showToast("Failed to save note: " + data.error, "error");
        }
    } catch(e) {
        showToast("Error communicating with server.", "error");
    } finally {
        if(btn) btn.disabled = false;
    }
}

async function loadSavedNotes() {
    const grid = document.getElementById('my-notes-grid');
    const empty = document.getElementById('my-notes-empty');
    if(!grid || !empty) return;

    try {
        const res = await fetch("/library");
        const data = await res.json();
        
        if(data.success) {
            savedNotesList = data.notes || [];
            
            if(savedNotesList.length === 0) {
                grid.classList.add('hidden');
                empty.classList.remove('hidden');
            } else {
                empty.classList.add('hidden');
                grid.classList.remove('hidden');
                
                // Build Cards
                grid.innerHTML = savedNotesList.map(note => {
                    let preview = "No content available.";
                    if(note.data && note.data['topic-overview']) {
                        preview = note.data['topic-overview'][0] || preview;
                    }

                    return `
                    <div class="saved-note-card">
                        <h3>${note.title}</h3>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem;">📅 ${note.date}</p>
                        <p class="sn-preview">${preview}</p>
                        <div style="display: flex; gap: 0.5rem; margin-top: auto;">
                            <button class="btn btn-primary" style="padding: 0.5rem; flex: 1;" onclick="viewNote(${note.id})">👁️ View</button>
                            <button class="btn btn-outline" style="padding: 0.5rem 1rem; color: var(--danger); border-color: var(--danger)" onclick="deleteNote(${note.id})" title="Delete">🗑️</button>
                        </div>
                    </div>
                    `;
                }).join('');
            }
        }
    } catch(e) {
        console.error("Failed to load notes library: ", e);
    }
}

async function updateDashboardStats() {
    // If list is empty, fetch it once
    if (savedNotesList.length === 0) {
        try {
            const res = await fetch("/library");
            const data = await res.json();
            if(data.success) {
                savedNotesList = data.notes || [];
            }
        } catch(e) {}
    }
    
    // Total
    const totalEl = document.getElementById('stat-total-notes');
    if(totalEl) totalEl.innerText = savedNotesList.length;
    
    // Saved notes
    const savedEl = document.getElementById('stat-saved-notes');
    if(savedEl) savedEl.innerText = savedNotesList.length;
    
    // Generated today
    const today = new Date().toLocaleDateString();
    const todayCount = savedNotesList.filter(n => n.date === today).length;
    const todayEl = document.getElementById('stat-today-notes');
    if(todayEl) todayEl.innerText = todayCount;
}

async function deleteNote(id) {
    if(!confirm("Are you sure you want to delete this note?")) return;
    
    try {
        const res = await fetch("/delete_note/" + id, { method: "DELETE" });
        const data = await res.json();
        if(data.success) {
            showToast("Note deleted successfully.", "error");
            await loadSavedNotes(); // refresh grid
        } else {
            showToast("Failed to delete note.", "error");
        }
    } catch(e) {
        showToast("Error communicating with server.", "error");
    }
}

function viewNote(id) {
    const note = savedNotesList.find(n => n.id === id);
    
    if(!note) return;
    
    document.getElementById('modal-title').textContent = note.title;
    document.getElementById('modal-date').textContent = "📅 " + note.date;
    
    // Unload dictionary to html
    let bodyHTML = "";
    Object.keys(note.data).forEach(sectionKey => {
        const readableTitle = sectionKey.replace('-', ' ').toUpperCase();
        let colorClass = sectionKey === 'topic-overview' ? 'var(--primary)' : 
                         sectionKey === 'key-points' ? 'var(--secondary)' : 'var(--accent)';
        
        bodyHTML += `<h4 style="color: ${colorClass}; margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.1rem;">${readableTitle}</h4>`;
        bodyHTML += `<ul style="padding-left: 1.2rem; margin-bottom: 1.5rem; line-height: 1.6;">`;
        note.data[sectionKey].forEach(str => {
            bodyHTML += `<li>${str}</li>`;
        });
        bodyHTML += `</ul>`;
    });
    
    document.getElementById('modal-body').innerHTML = bodyHTML;
    
    // Set active data for modal download button
    modalNoteDataTarget = note;

    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
    modalNoteDataTarget = null;
}

// ------ DOWNLOAD UTILS ------
function generateDownload(noteReference, filename) {
    if(!noteReference) return;
    
    let text = `--- ${noteReference.title} ---\nDate: ${noteReference.date}\n\n`;
    for(const [key, items] of Object.entries(noteReference.data)) {
        const title = key.replace('-', ' ').toUpperCase();
        text += `[ ${title} ]\n`;
        items.forEach(i => text += `• ${i}\n`);
        text += `\n`;
    }

    const blob = new Blob([text], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
}

function downloadNotes() {
    // Generate page download
    generateDownload(currentGeneratedNotes, "lecture_notes.txt");
}

function downloadFromModal() {
    // Modal popup download
    generateDownload(modalNoteDataTarget, "saved_lecture_notes.txt");
}

async function downloadPDF() {
    if(!currentGeneratedNotes) return;
    
    // Convert to text block for the backend FPDF
    let text = `--- ${currentGeneratedNotes.title} ---\nDate: ${currentGeneratedNotes.date}\n\n`;
    for(const [key, items] of Object.entries(currentGeneratedNotes.data)) {
        const title = key.replace('-', ' ').toUpperCase();
        text += `[ ${title} ]\n`;
        items.forEach(i => text += `• ${i}\n`);
        text += `\n`;
    }

    try {
        const res = await fetch("/download_pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text_content: text })
        });
        
        if(!res.ok) {
            const err = await res.json();
            showToast(err.error || "Failed to generate PDF.", "error");
            return;
        }
        
        const blob = await res.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "NotesAI_Summary.pdf";
        link.click();
        
    } catch(e) {
        showToast("Error communicating with server.", "error");
    }
}

// ------ FLASHCARDS & SETTINGS ENGINE ------
let flashcardsSet = [];
let currentCardIndex = 0;

function openFlashcardsMode() {
    if(!modalNoteDataTarget) return;
    
    // Convert data to flashcards (Q/A pairs)
    flashcardsSet = [];
    const data = modalNoteDataTarget.data;
    
    // We treat 'topic-overview' as general summary, let's use 'important-concepts' and 'key-points' for cards
    if(data['important-concepts']) {
        data['important-concepts'].forEach((concept, i) => {
            flashcardsSet.push({ front: `Important Concept ${i+1}`, back: concept });
        });
    }
    if(data['key-points']) {
        data['key-points'].forEach((point, i) => {
            flashcardsSet.push({ front: `Key Point ${i+1}`, back: point });
        });
    }
    
    if(flashcardsSet.length === 0) {
        showToast("No flashcard data available for this note.", "error"); return;
    }
    
    currentCardIndex = 0;
    renderFlashcard();
    
    document.getElementById('flashcard-overlay').classList.remove('hidden');
    
    // Hide the main modal behind it
    document.getElementById('modal-overlay').classList.add('hidden');
}

function closeFlashcards() {
    document.getElementById('flashcard-overlay').classList.add('hidden');
    // Pop back to the normal modal
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function renderFlashcard() {
    const card = flashcardsSet[currentCardIndex];
    document.getElementById('fc-front-text').innerHTML = card.front;
    document.getElementById('fc-back-text').innerHTML = card.back;
    document.getElementById('fc-progress').innerText = `Card ${currentCardIndex + 1} of ${flashcardsSet.length}`;
    
    // reset flip
    document.getElementById('fc-inner').classList.remove('is-flipped');
}

function flipCard() {
    document.getElementById('fc-inner').classList.toggle('is-flipped');
}

function nextCard() {
    if(currentCardIndex < flashcardsSet.length - 1) {
        currentCardIndex++;
        renderFlashcard();
    } else {
        showToast("You've completed this deck!", "success");
    }
}

function prevCard() {
    if(currentCardIndex > 0) {
        currentCardIndex--;
        renderFlashcard();
    }
}

async function deleteAllNotes() {
    if(!confirm("WARNING: This will permanently wipe all your saved notes. Proceed?")) return;
    
    try {
        const res = await fetch("/delete_all_notes", { method: "DELETE" });
        const data = await res.json();
        if(data.success) {
            showToast("Notes library cleared successfully.", "success");
            await loadSavedNotes();
            navigateDashboard('view-mynotes'); // Hop back to library to see it empty
        } else {
            showToast("Failed to clear notes.", "error");
        }
    } catch(e) {
        showToast("Error communicating with server.", "error");
    }
}
