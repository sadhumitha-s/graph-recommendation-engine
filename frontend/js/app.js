const API_URL = "http://localhost:8000";

// --- State Management ---
const AppState = {
    userId: localStorage.getItem('graph_user_id') || 1,
    
    setUserId: function(id) {
        this.userId = id;
        localStorage.setItem('graph_user_id', id);
        // Dispatch event so other parts of UI can update
        window.dispatchEvent(new Event('userChanged'));
    }
};

// --- API Interactions ---

async function fetchItems() {
    try {
        const res = await fetch(`${API_URL}/items`);
        return await res.json();
    } catch (e) {
        console.error("API Error:", e);
        return {};
    }
}

async function fetchRecommendations() {
    const userId = AppState.userId;
    try {
        const res = await fetch(`${API_URL}/recommend/${userId}?k=5`);
        return await res.json();
    } catch (e) {
        console.error("Rec Error:", e);
        return null;
    }
}

async function fetchMetrics() {
    try {
        const res = await fetch(`${API_URL}/metrics/`);
        return await res.json();
    } catch (e) {
        return null;
    }
}

async function toggleInteraction(itemId, isUnlike) {
    const userId = AppState.userId;
    const method = isUnlike ? 'DELETE' : 'POST'; // Switch method

    try {
        const res = await fetch(`${API_URL}/interaction/`, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: parseInt(userId), item_id: itemId })
        });
        
        if(res.ok) {
            console.log(isUnlike ? "Unliked" : "Liked");
            return true;
        }
        return false;
    } catch (e) {
        console.error("API Error", e);
        return false;
    }
}

// --- NEW FUNCTION: Fetch history ---
async function fetchUserLikes() {
    const userId = AppState.userId;
    try {
        const res = await fetch(`${API_URL}/interaction/${userId}`);
        if (res.ok) {
            return await res.json(); // Returns array like [101, 102]
        }
        return [];
    } catch (e) {
        console.error("Error fetching likes:", e);
        return [];
    }
}

// --- Shared UI Helpers ---

function updateUserIdDisplay() {
    const inputs = document.querySelectorAll('.user-id-input');
    inputs.forEach(input => input.value = AppState.userId);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateUserIdDisplay();
    
    // Listen for manual changes to inputs
    document.querySelectorAll('.user-id-input').forEach(input => {
        input.addEventListener('change', (e) => {
            AppState.setUserId(e.target.value);
        });
    });
});