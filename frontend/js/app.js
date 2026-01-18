const API_URL = ""; 
let supabase = null;

const AppState = {
    myId: null,       // Authenticated ID
    viewingId: 1,     // ID displayed on screen
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
        // 1. Fetch Env Config from Backend
        const configRes = await fetch(`${API_URL}/api/config`);
        if (!configRes.ok) throw new Error("Failed to fetch config");
        const config = await configRes.json();

        if (!config.supabase_url || !config.supabase_key) {
            console.error("Supabase config missing");
            return;
        }

        // 2. Init Client
        supabase = window.supabase.createClient(config.supabase_url, config.supabase_key);

        // 3. Check Auth
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
            await setupUser(session);
        } else {
            updateAuthButton(null);
            // Even if guest, load data for default viewingId (1)
            window.dispatchEvent(new Event('appReady'));
        }
    } catch (e) {
        console.error("Init Error:", e);
    }
}

async function setupUser(session) {
    AppState.token = session.access_token;
    
    // Get Graph ID
    const { data } = await supabase.from('profiles').select('id').eq('uuid', session.user.id).single();
    
    if (data) {
        AppState.myId = data.id;
        // If first load, show MY profile
        if (!window.hasSetInitialView) {
            AppState.viewingId = data.id;
            window.hasSetInitialView = true;
        }
    }
    
    updateAuthButton(session.user.email);
    window.dispatchEvent(new Event('userChanged'));
    window.dispatchEvent(new Event('appReady'));
}

function updateAuthButton(email) {
    const container = document.getElementById('nav-auth-container');
    if (!container) return;

    if (email) {
        // Logged In: Show Avatar
        // Using a generic avatar service based on email
        container.innerHTML = `
            <div class="flex items-center gap-3">
                <img src="https://ui-avatars.com/api/?name=${email}&background=0D8ABC&color=fff&size=32" class="w-8 h-8 rounded-full border border-gray-600" title="${email}">
                <button onclick="logout()" class="text-sm text-red-400 hover:text-white transition">Logout</button>
            </div>
        `;
    } else {
        // Guest: Show Login Link
        container.innerHTML = `
            <a href="login" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded text-sm font-bold transition">Login / Register</a>
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
        alert("You are in Guest Mode or viewing another user.\n\nPlease login and view your own profile to edit.");
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