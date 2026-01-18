const API_URL = ""; 
let supabase = null;

// Global Flag to prevent race conditions
window.appIsReady = false;

const AppState = {
    myId: null,       
    viewingId: 1,     
    token: null,      
    algo: localStorage.getItem('graph_algo') || 'bfs',
    selectedGenres: new Set(),

    canEdit: function() {
        return this.myId !== null && this.myId === this.viewingId;
    },

    setViewingId: function(id) {
        this.viewingId = parseInt(id) || 1;
        window.dispatchEvent(new Event('userChanged'));
    },

    setAlgo: function(algo) {
        this.algo = algo;
        localStorage.setItem('graph_algo', algo);
    }
};

// --- CORE INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    await initSupabase();
});

async function initSupabase() {
    try {
        const configRes = await fetch(`${API_URL}/api/config`);
        
        if (!configRes.ok) {
            console.warn("Backend Config API failed. Running in Guest Mode.");
            finalizeInit(null);
            return;
        }

        const config = await configRes.json();

        if (config.supabase_url && config.supabase_key) {
            supabase = window.supabase.createClient(config.supabase_url, config.supabase_key);
            const { data: { session } } = await supabase.auth.getSession();
            if (session) {
                await setupUser(session);
            } else {
                finalizeInit(null);
            }
        } else {
            finalizeInit(null);
        }
    } catch (e) {
        console.error("Init Failure:", e);
        finalizeInit(null);
    }
}

// Helper to fire the ready event reliably
function finalizeInit(email) {
    updateAuthButton(email);
    window.appIsReady = true; // Set flag
    window.dispatchEvent(new Event('appReady'));
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
    if (!container) return;

    if (email) {
        container.innerHTML = `
            <div class="flex items-center gap-3">
                <img src="https://ui-avatars.com/api/?name=${email}&background=6366f1&color=fff&size=32" style="width:32px; height:32px; border-radius:50%; border:1px solid #444;">
                <button onclick="logout()" style="background:transparent; border:none; color:#f87171; font-size:0.85rem; cursor:pointer;">Logout</button>
            </div>
        `;
    } else {
        container.innerHTML = `
            <a href="login.html" class="btn-login" style="background:#3b82f6; color:white; padding:8px 16px; border-radius:8px; text-decoration:none; font-weight:bold; font-size:0.9rem;">Login / Register</a>
        `;
    }
}

async function logout() {
    if(supabase) await supabase.auth.signOut();
    window.location.href = "index.html";
}

// --- DATA FETCHING ---

async function fetchItems() {
    try {
        const res = await fetch(`${API_URL}/items`);
        return await res.json();
    } catch (e) { return []; }
}

async function toggleInteraction(itemId, isUnlike) {
    if (!AppState.canEdit()) {
        alert("Read-Only Mode. Login to edit.");
        return false;
    }

    const method = isUnlike ? 'DELETE' : 'POST';
    try {
        const res = await fetch(`${API_URL}/interaction/`, {
            method: method,
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${AppState.token}`
            },
            body: JSON.stringify({ user_id: AppState.myId, item_id: itemId })
        });
        return res.ok;
    } catch (e) { return false; }
}

async function fetchUserLikes(targetId) {
    const id = targetId || AppState.viewingId;
    try {
        const res = await fetch(`${API_URL}/interaction/${id}`);
        return res.ok ? await res.json() : [];
    } catch (e) { return []; }
}

async function fetchRecommendations() {
    try {
        const res = await fetch(`${API_URL}/recommend/${AppState.viewingId}?k=5&algo=${AppState.algo}`);
        return await res.json();
    } catch (e) { return null; }
}

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_URL}/metrics/`);
        return await res.json();
    } catch (e) { return null; }
}

async function savePreferences() {
    if (!AppState.canEdit()) return;
    const genres = Array.from(AppState.selectedGenres);
    await fetch(`${API_URL}/recommend/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: AppState.myId, genres: genres })
    });
}