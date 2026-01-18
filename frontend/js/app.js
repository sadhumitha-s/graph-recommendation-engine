const API_URL = ""; 

// --- CRITICAL CONFIGURATION ---
const SUPABASE_URL = "https://rgqiezjbzraidrlmkjkm.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJncWllempienJhaWRybG1ramttIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Mjc1NzIsImV4cCI6MjA4MzEwMzU3Mn0.9HCCW8Lgaw53rOwMQbpzlqVu34l3vpgknkcxN_HidNM";

let supabaseClient = null;
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
    console.log("[App] DOMContentLoaded fired");
    
    try {
        if (window.supabase) {
            console.log("[App] Supabase library found");
            try {
                supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
                console.log("[App] Supabase client created");
                
                try {
                    const { data: { session } } = await supabaseClient.auth.getSession();
                    if (session) {
                        console.log("[App] Session found for:", session.user.email);
                        await setupUser(session);
                        return;
                    }
                } catch (e) {
                    console.error("[App] Auth check failed:", e);
                }
            } catch (e) {
                console.error("[App] Supabase init failed:", e);
            }
        } else {
            console.warn("[App] Supabase library not loaded");
        }
    } catch (e) {
        console.error("[App] Unexpected error during init:", e);
    }
    
    console.log("[App] Initializing in guest mode");
    finalizeInit(null);
});

function finalizeInit(email) {
    console.log("[App] finalizeInit - email:", email, "myId:", AppState.myId);
    updateAuthButton(email);
    
    if (!window.appIsReady) {
        window.appIsReady = true;
        console.log("[App] 🎯 Dispatching appReady event");
        window.dispatchEvent(new Event('appReady'));
    }
}

async function setupUser(session) {
    console.log("[App] setupUser called for:", session.user.email);
    AppState.token = session.access_token;
    
    try {
        const res = await fetch(`${API_URL}/auth/user-id`, {
            headers: { 'Authorization': `Bearer ${AppState.token}` }
        });
        
        if (res.ok) {
            const { user_id } = await res.json();
            AppState.myId = user_id;
            // Set to their own ID on first login
            if (!sessionStorage.getItem('loginShown')) {
                AppState.viewingId = user_id;
                sessionStorage.setItem('loginShown', 'true');
            }
            console.log("[App] User ID:", AppState.myId);
        } else {
            console.warn("[App] Could not fetch user ID");
        }
    } catch (e) {
        console.warn("[App] User ID fetch failed:", e);
    }
    
    finalizeInit(session.user.email);
    window.dispatchEvent(new Event('userChanged'));
}

function updateAuthButton(email) {
    const container = document.getElementById('nav-auth-container');
    if (!container) return;

    if (email) {
        const initial = email.charAt(0).toUpperCase();
        const logoutBtn = `<button onclick="logout()" style="background:transparent; border:none; color:#f87171; cursor:pointer; font-size:0.9rem;">Logout</button>`;
        container.innerHTML = `
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="width:32px; height:32px; border-radius:50%; background:#6366f1; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:0.8rem;">
                    ${initial}
                </div>
                ${logoutBtn}
            </div>`;
    } else {
        container.innerHTML = `<a href="login.html" class="btn-login" style="background:#2563eb; color:white; padding:8px 16px; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.9rem; display:inline-block;">Login / Register</a>`;
    }
}

async function logout() {
    await supabaseClient.auth.signOut();
    window.location.href = "index.html";
}

// --- API ACTIONS ---
async function fetchItems() {
    try {
        const res = await fetch(`${API_URL}/items`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) { 
        console.error("[API] fetchItems:", e);
        return []; 
    }
}

async function toggleInteraction(itemId, isUnlike) {
    if (!AppState.canEdit()) { alert("Login to edit your own profile."); return false; }
    const method = isUnlike ? 'DELETE' : 'POST';
    try {
        const res = await fetch(`${API_URL}/interaction/`, {
            method: method,
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AppState.token}` },
            body: JSON.stringify({ user_id: AppState.myId, item_id: itemId })
        });
        return res.ok;
    } catch (e) { 
        console.error("[API] toggleInteraction:", e);
        return false; 
    }
}

async function fetchUserLikes(targetId) {
    const id = targetId || AppState.viewingId;
    try {
        const res = await fetch(`${API_URL}/interaction/${id}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) { 
        console.error("[API] fetchUserLikes:", e);
        return []; 
    }
}

async function fetchRecommendations() {
    try {
        const res = await fetch(`${API_URL}/recommend/${AppState.viewingId}?k=5&algo=${AppState.algo}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) { 
        console.error("[API] fetchRecommendations:", e);
        return null; 
    }
}

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_URL}/metrics/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) { 
        console.error("[API] fetchMetrics:", e);
        return null; 
    }
}

async function savePreferences() {
    if (!AppState.canEdit()) return;
    const genres = Array.from(AppState.selectedGenres);
    try {
        await fetch(`${API_URL}/recommend/preferences`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AppState.token}` },
            body: JSON.stringify({ user_id: AppState.myId, genres: genres })
        });
    } catch (e) {
        console.error("[API] savePreferences:", e);
    }
}