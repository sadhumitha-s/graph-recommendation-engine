const API_URL = ""; 
let supabase; // Initialize dynamically

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

// --- INITIALIZATION ---

document.addEventListener('DOMContentLoaded', async () => {
    try {
        // 1. Fetch Config from Backend
        const configRes = await fetch(`${API_URL}/api/config`);
        const config = await configRes.json();
        
        if (!config.supabase_url || !config.supabase_key) {
            console.error("Supabase config missing from backend.");
            return;
        }

        // 2. Initialize Supabase
        supabase = window.supabase.createClient(config.supabase_url, config.supabase_key);

        // 3. Check Session
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
            await setupUser(session);
        } else {
            renderAuthUI(false);
        }
    } catch (e) {
        console.error("Failed to initialize app:", e);
    }
});

// --- AUTH & STATE ---

async function setupUser(session) {
    AppState.token = session.access_token;
    
    const { data } = await supabase.from('profiles').select('id').eq('uuid', session.user.id).single();
    
    if (data) {
        AppState.myId = data.id;
        if (!window.hasSetInitialView) {
            AppState.viewingId = data.id;
            window.hasSetInitialView = true;
        }
    }
    
    const emailEl = document.getElementById('user-email-display');
    if (emailEl) emailEl.innerText = session.user.email;
    
    renderAuthUI(true);
    window.dispatchEvent(new Event('userChanged'));
}

function renderAuthUI(isLoggedIn) {
    const guestDiv = document.getElementById('auth-ui-guest');
    const userDiv = document.getElementById('auth-ui-user');
    
    if (guestDiv && userDiv) {
        if (isLoggedIn) {
            guestDiv.style.display = 'none';
            userDiv.style.display = 'flex';
        } else {
            guestDiv.style.display = 'block';
            userDiv.style.display = 'none';
        }
    }
}

// --- MODAL ACTIONS ---
function openLogin() { 
    const modal = document.getElementById('login-modal');
    if(modal) modal.style.display = 'flex'; 
}
function closeLogin() { 
    const modal = document.getElementById('login-modal');
    if(modal) modal.style.display = 'none'; 
}

async function handleAuth(type) {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorBox = document.getElementById('auth-error');
    
    let result;
    if (type === 'signup') {
        result = await supabase.auth.signUp({ email, password });
    } else {
        result = await supabase.auth.signInWithPassword({ email, password });
    }

    if (result.error) {
        if(errorBox) {
            errorBox.innerText = result.error.message;
            errorBox.style.display = 'block';
        }
    } else {
        closeLogin();
        location.reload(); 
    }
}

async function logout() {
    await supabase.auth.signOut();
    location.reload();
}

// --- API WRAPPERS ---

async function fetchItems() {
    try {
        const res = await fetch(`${API_URL}/items`);
        return await res.json();
    } catch (e) { return []; }
}

async function toggleInteraction(itemId, isUnlike) {
    if (!AppState.canEdit()) {
        alert("You are in Read-Only mode. Login and view your own profile to edit.");
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
        
        if (res.status === 403) {
            alert("Security Error: You are not authorized to modify this user.");
            return false;
        }
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