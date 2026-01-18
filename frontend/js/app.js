const API_URL = ""; 

// --- CRITICAL CONFIGURATION ---
const SUPABASE_URL = "https://rgqiezjbzraidrlmkjkm.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJncWllempienJhaWRybG1ramttIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Mjc1NzIsImV4cCI6MjA4MzEwMzU3Mn0.9HCCW8Lgaw53rOwMQbpzlqVu34l3vpgknkcxN_HidNM";

let supabase = null;
window.appIsReady = false;

const AppState = {
    myId: null,       
    viewingId: 1,     
    token: null,      
    algo: localStorage.getItem('graph_algo') || 'bfs',
    selectedGenres: new Set(),

    canEdit: function() { return this.myId !== null && this.myId === this.viewingId; },
    setViewingId: function(id) { this.viewingId = parseInt(id) || 1; window.dispatchEvent(new Event('userChanged')); },
    setAlgo: function(algo) { this.algo = algo; localStorage.setItem('graph_algo', algo); }
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initialize Supabase (with fallback)
    if (window.supabase) {
        try {
            supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
            
            // 2. Check Auth Status
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (session) {
                    await setupUser(session);
                } else {
                    finalizeInit(null); // Guest Mode
                }
            } catch (e) {
                console.error("Auth Status Check Failed:", e);
                finalizeInit(null); // Fallback to Guest
            }
        } catch (e) {
            console.error("Supabase Init Failed:", e);
            finalizeInit(null); // Fallback to Guest if Supabase fails
        }
    } else {
        console.warn("Supabase library not loaded. Running in Guest Mode.");
        finalizeInit(null);
    }
});

function finalizeInit(email) {
    updateAuthButton(email);
    // Set global flag and fire event for HTML pages
    if (!window.appIsReady) {
        window.appIsReady = true;
        window.dispatchEvent(new Event('appReady'));
    }
}

async function setupUser(session) {
    AppState.token = session.access_token;
    // Attempt to get Graph ID
    const { data } = await supabase.from('profiles').select('id').eq('uuid', session.user.id).single();
    if (data) {
        AppState.myId = data.id;
        if (!window.hasSetInitialView) {
            AppState.viewingId = data.id;
            window.hasSetInitialView = true;
        }
    }
    finalizeInit(session.user.email);
    window.dispatchEvent(new Event('userChanged'));
}

function updateAuthButton(email) {
    const container = document.getElementById('nav-auth-container');
    if (!container) {
        console.warn("nav-auth-container not found");
        return;
    }

    if (email) {
        container.innerHTML = `
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="width:32px; height:32px; border-radius:50%; background:#6366f1; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:0.8rem;">
                    ${email.charAt(0).toUpperCase()}
                </div>
                <button onclick="logout()" style="background:transparent; border:none; color:#f87171; cursor:pointer; font-size:0.9rem;">Logout</button>
            </div>`;
    } else {
        // Guest Mode - Show Login Button
        container.innerHTML = `<a href="login.html" class="btn-login" style="background:#2563eb; color:white; padding:8px 16px; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.9rem; display:inline-block;">Login / Register</a>`;
    }
}

async function logout() {
    await supabase.auth.signOut();
    window.location.href = "index.html";
}

// --- API ACTIONS ---
async function fetchItems() {
    try {
        const res = await fetch(`${API_URL}/items`);
        if (!res.ok) throw new Error("API Error");
        return await res.json();
    } catch { return []; }
}

async function toggleInteraction(itemId, isUnlike) {
    if (!AppState.canEdit()) { alert("Login to edit."); return false; }
    const method = isUnlike ? 'DELETE' : 'POST';
    try {
        const res = await fetch(`${API_URL}/interaction/`, {
            method: method,
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AppState.token}` },
            body: JSON.stringify({ user_id: AppState.myId, item_id: itemId })
        });
        return res.ok;
    } catch { return false; }
}

async function fetchUserLikes(targetId) {
    const id = targetId || AppState.viewingId;
    try {
        const res = await fetch(`${API_URL}/interaction/${id}`);
        return res.ok ? await res.json() : [];
    } catch { return []; }
}

async function fetchRecommendations() {
    try {
        const res = await fetch(`${API_URL}/recommend/${AppState.viewingId}?k=5&algo=${AppState.algo}`);
        return await res.json();
    } catch { return null; }
}

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_URL}/metrics/`);
        return await res.json();
    } catch { return null; }
}

async function savePreferences() {
    if (!AppState.canEdit()) return;
    const genres = Array.from(AppState.selectedGenres);
    await fetch(`${API_URL}/recommend/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AppState.token}` },
        body: JSON.stringify({ user_id: AppState.myId, genres: genres })
    });
}