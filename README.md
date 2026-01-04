# Graph-based Reccommendations System

- **Hybrid Architecture:** FastAPI orchestrates logic, while a compiled C++17 extension handles $O(1)$ graph mutations.
- **Bipartite Graph Logic:** Uses Breadth-First Search (BFS) to traverse User $\leftrightarrow$ Item connections for transparent, deterministic recommendations.
- **Waterfall Strategy:** Cascades from Personalized Graph $\to$ Global Trending $\to$ Catalog to ensure zero empty states.
- **Time-Decay Scoring:** Applies gravity decay formulas within the C++ engine to prioritize recent interactions.
- **Real-Time Updates:** Instantly updates the in-memory graph structure upon every "Like" or "Unlike".

---

### Quick Start

1. **Compile the C++ Engine**
   You must compile the core engine before running the Python backend.
```bash
cd cpp_engine/build
cmake ..
make
mv recommender*.so ../../backend/
```  
  
2. **Start the backend**  
```bash
cd path\to\graph-recommendation-engine\backend\
uvicorn app.main:app --reload
```

3. **Start the frontend**  
   In a new terminal:
```bash
cd path\to\graph-recommendation-engine\frontend\
python3 -m http.server 3000
```
3. Go to http://localhost:3000 to interact with the system.
