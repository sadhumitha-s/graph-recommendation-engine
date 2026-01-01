# Graph-based Reccommendations System

GraphRec is a fast recommendation engine that blends Python and C++ for instant, deterministic suggestions.

- FastAPI handles the API, while a compiled C++17 extension does the heavy graph work
- Uses BFS on a bipartite graph to find user similarities
- Python and C++ talk seamlessly via pybind11 for low-latency, zero-copy communication
- Built with standard C++ libraries (unordered_map, vector) for speed and portability
- Updates the in-memory graph in real time with every user interaction
- Serves as a blueprint for speeding up Python apps without leaving the ecosystem

## To Run:
1. **Start the backend**  
   Open a terminal and run: 
```bash
cd path\to\graph-recommendation-engine\backend\
uvicorn app.main:app --reload
```
2. **Start the frontend**  
   In a separate terminal, run:
```bash
cd path\to\graph-recommendation-engine\frontend\
python3 -m http.server 3000
```
3. Go to http://localhost:3000 on your browser to view the application.
