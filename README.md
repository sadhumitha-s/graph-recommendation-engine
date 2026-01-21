# **GraphRec Engine (Hybrid C++ & Python)**  
A high-performance Recommendation Engine built with a hybrid architecture. It combines the speed of a custom C++ Graph Engine for traversal algorithms (BFS, PageRank) with the flexibility of Python/FastAPI for the web layer.

[Live Demo](https://graphrec-engine.onrender.com)  
*(Note: App hosted on free tier, may spin down after inactivity. Please wait 30s for wakeup!)*

## Features
* **Hybrid Architecture:** FastAPI orchestrates logic, while a compiled C++17 extension handles $O(1)$ graph mutations.  
* **Dual Algorithms:** switches between **Weighted BFS** (Local/Deterministic) and **Personalized PageRank** (Global/Probabilistic) strategies.  
* **Smart Caching:** implements a 'Cache-Aside' pattern using Redis (Local or Upstash) to serve frequent requests in <1ms, with automatic SSL handling for cloud environments.  
* **Self-Healing State:** serializes the C++ graph to a binary blob (graph.bin) for $O(1)$ startup.Automatically detects corruption/empty states and falls back to a **SQL Rebuild** to ensure data integrity.  
* **Content-Aware Scoring:** dynamically boosts graph edge weights based on user genre preferences.  
* **Waterfall Strategy:** cascades from Graph Algo $\\to$ Global Trending $\\to$ Catalog to ensure zero empty states.
* **Graceful Persistence:** automatically captures graph state changes on server shutdown (SIGTERM), syncing the in-memory graph to Postgres to survive container restarts.
* **Cloud-Native:** fully Dockerized single-container architecture that auto-configures for Local (SQLite/Local Redis) or Production (Supabase/Upstash) environments via environment variables.  
* **User Authentication & Authorization:** Supabase Auth integration with JWT verification enables secure multi-user support. Guest mode allows exploration(read-only); registered users can maintain preferences and curated collections.
* **Role-Based Access Control:** logged-in users can edit their own likes and preferences with full edit access; all users can view other profiles in read-only mode, with granular permission checks on interactions.
* **Genre Preferences:** users can select genre tags to personalize recommendations; preferences are stored and dynamically influence graph traversal scoring.

---  

## **Architecture**  
The system uses a single-container hybrid approach for maximum efficiency:  
1. **Auth Layer (Supabase JWT):** Handles user registration, login, and token verification. Backend validates JWTs and maps Supabase UUIDs to internal graph user IDs.  
2. **Compute Layer (C++):** A custom-built graph engine (using Pybind11) handles memory-intensive graph traversals (BFS, Personalized PageRank) in milliseconds.  
3. **API Layer (Python):** FastAPI handles HTTP requests, enforces authorization rules, and orchestrates the C++ module.
4. **Storage (Supabase/Postgres):** Persists user profiles, interactions (Likes/Dislikes), and genre preferences.
5. **Cache (Upstash/Redis):** Caches recommendation results and invalidates intelligently on user edits.
6. **State Management:** The graph state is computed in memory and snapshotted to the database on server shutdown.
  
---  

## **Project Structure**
```pqsql
graphrec-engine/  
│  
├── .dockerignore           # Docker build exclusions  
├── Dockerfile              # Multi-stage build (Compiles C++ & Runs Python)  
├── docker-compose.yml      # Orchestrates Backend, Frontend, and Redis  
│
├── render.yaml             # Render.com Deployment Blueprint
│
├── backend/                 
│   ├── recommender\*.so    # Compiled C++ Module  
│   ├── graph.bin           # Binary Graph Snapshot (Fast Load)  
│   │  
│   └── app/  
│       ├── main.py         # App Entry: Handles Auth, Binary Loading & DB Sync  
│       ├── config.py       # Configures SQLite/Postgres, Redis, & URLs  
│       ├── api/            # Endpoints (Auth, Interactions, Recommendations)  
│       ├── core/           # Redis Client, C++ Wrapper, JWT security  
│       └── db/             # SQL Models (Profiles, Interactions, Preferences) & CRUD
│  
├── cpp_engine/             # High-Performance Core  
│   ├── include/            # Headers  
│   └── src/  
│       ├── RecommendationEngine.cpp  # BFS, PageRank, & Serialization Logic  
│       └── bindings.cpp    # Pybind11 hooks  
│  
├── frontend/               
│   ├── index.html          # Main UI (Discover page with Taste profile)
│   ├── recommendations.html      # Recommendations (For you) page
|   ├── login.html          # Auth UI (Register & Login)
│   ├── css/styles.css      # Responsive glass-morphism design
│   └── js/app.js           # API Logic, State Management, & Auth Flow  
│  
└── docs/                   # Documentation
    ├── architecture.md             
    ├── algorithms.md               
    └── complexity.md               
```  
  
---  

## **User Flow**

**Guest Mode (Anonymous Browse)**
- No login required
- Browse all movies and user profiles
- View recommendations for any user (read-only)
- Cannot like/dislike or set preferences

**Registered User (Authenticated Edit)**
- Sign up or login via Supabase Auth
- Automatically assigned a sequential user ID (1, 2, 3, ...)
- Full edit access to own profile (likes, dislikes, genre preferences)
- Preferences dynamically influence personalized recommendations
- Can still browse and view other profiles in read-only mode

**Permission Model**
- `canEdit()` returns `true` only when `myId == viewingId` (your own profile)
- All interactions (POST/DELETE) require JWT verification
- Profile data is visible to all; only owner can modify

---  

## **Quick Start(Local Docker)**  
**1. Clone & Configure**  
```bash
git clone [https://github.com/YOUR_USERNAME/GraphRec.git](https://github.com/YOUR_USERNAME/GraphRec.git)
cd GraphRec

# Create environment file
touch backend/.env
```
**2. Set up Environment Variables**  
Add your credentials to `backend/.env`  
```bash
DATABASE_URL="postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres"
REDIS_URL="redis://localhost:6379/0"
SUPABASE_URL="https://[PROJECT].supabase.co"
SUPABASE_ANON_KEY="eyJ..."
SUPABASE_JWT_SECRET="[JWT_SIGNING_SECRET]"
```  

**3. Run**  
```bash
docker-compose up --build
```
Access the app at http://localhost:8000.  
  
---  

## **Performance**  
| Operation | Latency | Notes |
|-----------|---------|-------|
| BFS Traversal | <10ms | Local graph, $O(V+E)$ |
| PageRank (PPR) | 20–50ms | 10 iterations, sparsity-aware |
| Redis Cache Hit | <1ms | 1-hour TTL |
| Graph Load (snapshot) | <100ms | Binary deserialization |
| DB Sync (cold start) | <500ms | Replay all interactions |  

  
