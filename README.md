# **Graph-based Recommendations System**

* **Hybrid Architecture:** FastAPI orchestrates logic, while a compiled C++17 extension handles $O(1)$ graph mutations.  
* **Dual Algorithms:** Switches between **Weighted BFS** (Local/Deterministic) and **Personalized PageRank** (Global/Probabilistic) strategies.  
* **Redis Caching:** Implements a 'Cache-Aside' pattern to serve frequent recommendation requests in \<1ms.  
* **Instant Startup:** Serializes the C++ graph to a binary blob (graph.bin), reducing cold boot time from $O(E)$ to $O(1)$ disk I/O.  
* **Content-Aware Scoring:** Dynamically boosts graph edge weights based on user genre preferences.  
* **Waterfall Strategy:** Cascades from Graph Algo $\\to$ Global Trending $\\to$ Catalog to ensure zero empty states.  
* **Cloud-Ready:** seamless integration with PostgreSQL (Supabase) and Docker containerization.
  
---  

## **Project Structure**
```pqsql
graphrec-engine/  
│  
├── .dockerignore           \# Docker build exclusions  
├── Dockerfile              \# Multi-stage build (Compiles C++ & Runs Python)  
├── docker-compose.yml      \# Orchestrates Backend, Frontend, and Redis  
│  
├── backend/                \# FastAPI Orchestrator  
│   ├── recommender\*.so     \# Compiled C++ Module  
│   ├── graph.bin           \# Binary Graph Snapshot (Fast Load)  
│   │  
│   └── app/  
│       ├── main.py         \# App Entry: Handles Binary Loading & DB Sync  
│       ├── config.py       \# Configures SQLite/Postgres & Redis URLs  
│       ├── api/            \# Endpoints (Interactions, Recommendations)  
│       ├── core/           \# Redis Client & C++ Wrapper  
│       └── db/             \# SQL Models & CRUD  
│  
├── cpp\_engine/             \# High-Performance Core  
│   ├── include/            \# Headers  
│   └── src/  
│       ├── RecommendationEngine.cpp \# BFS, PageRank, & Serialization Logic  
│       └── bindings.cpp    \# Pybind11 hooks  
│  
├── frontend/               \# Client Application  
│   ├── index.html          \# Main UI: Dashboard & Glassmorphism Styles  
│   ├── recommendations.html  
│   └── js/app.js           \# API Logic & State Management  
│  
└── docs/                   \# Documentation
    ├── architecture.md             
    ├── algorithms.md               
    └── complexity.md               
```  
  
---  

## **Quick Start**

### **Option A: Docker (Recommended)**

Builds the C++ engine inside Linux, sets up Redis, and starts the app automatically.

docker-compose up \--build
  
---    
  
### **Option B: Manual Setup (Mac/Linux)**

1. **Compile the C++ Engine**  
   cd cpp\_engine/build  
   cmake ..  
   make  
   mv recommender\*.so ../../backend/

2. Start Infrastructure  
   Ensure Redis is running in a separate terminal (redis-server).

3. **Start Backend**  
   cd backend  
   uvicorn app.main:app \--reload

4. **Start Frontend**  
   cd frontend  
   python3 \-m http.server 3000

**Access the App:** Go to [http://localhost:3000](https://www.google.com/search?q=http://localhost:3000)