# System Architecture

## Overview

The Graph-Based Recommendation System is a hybrid application designed for high-performance personalized suggestions. It bridges Python’s ecosystem ease with C++’s computational speed, implementing a **Waterfall recommendation strategy** that handles everything from real-time personalized graphs to cold-start scenarios.

---

## High-Level Design
```text
[ User / Browser ]
       ^
       | HTTP/JSON (Fetch, Toggle Like)
       v
+-----------------------+
|    FastAPI Backend    |  <--- Orchestrator: Filters History, Manages Fallbacks
|      (Python)         |
+----------+------------+
           |
           |
    +------+-------+-------------------------+
    |              |                         |
    v              v                         v
+-------+    +--------------------------+  +---------------------+
| MySQL |    |   C++ Recommendation     |  |   Logic Layers      |
|  DB   |    |         Engine           |  | 1. Graph (C++)      |
+-------+    | (Compiled .so Extension) |  | 2. Trending (SQL)   |
             +--------------------------+  | 3. Catalog (SQL)    |
                                           +---------------------+

```
## **Components**

### **1\. Frontend (Presentation Layer)**

* **Tech**: HTML5, CSS3, Vanilla JavaScript.  
* **Role**:  
  * **Dynamic UI**: Toggles item states (Blue/White) instantly.  
  * **State Management**: Fetches user history on load (GET /interaction/{uid}) to persist "Like" states across refreshes.  
  * **Feedback**: Displays the *Reason* for a recommendation (e.g., "Graph-Based" vs "Global Trending").

### **2\. Backend (Orchestration Layer)**

* **Tech**: Python 3, FastAPI, SQLAlchemy.  
* **Role**:  
  * **API Gateway**: Exposes POST/DELETE for interactions and GET for recommendations.  
  * **Sanitization**: Enforces a strict "Blocklist" to ensure users never see items they have already liked.  
  * **Hybrid Logic**: Implements a Cascading Strategy mechanism. If the C++ engine returns no results, it seamlessly falls back to SQL aggregation queries (Most Popular).

### **3\. Core Engine (Computation Layer)**

* **Tech**: C++17, STL (Standard Template Library).  
* **Role**:  
  * **In-Memory Graph**: Stores user-item interactions as adjacency lists.  
  * **Time-Decay Scoring**: Edges store timestamps. The algorithm applies a gravity decay formula to prioritize recent interactions over old ones.  
  * **Operations**: Supports $O(1)$ amortized insertion and removal of edges.

### **4\. Database (Persistence Layer)**

* **Tech**: MySQL (Production) or SQLite (Dev).  
* **Role**: Source of truth. Stores persistence data and handles "Global Trending" queries (e.g., GROUP BY item\_id ORDER BY COUNT(\*) DESC).

## **Data Flow**

### **1\. Write Path (Like / Unlike)**

When a user interacts with an item:

1. **Frontend**: Sends POST (Like) or DELETE (Unlike) to /interaction.  
2. **Backend**:  
   * **Persistence**: Inserts/Deletes the row in the SQL Database.  
   * **Synchronization**: Immediately calls engine.add\_interaction() or engine.remove\_interaction() in C++.  
3. **Result**: The In-Memory Graph is updated instantly. The next recommendation request reflects this change immediately.

### **2\. Read Path (The "Waterfall" Strategy)**

When a user requests recommendations (GET /recommend/{user\_id}), the system executes a 3-step cascade:

* **Step 0: History Fetching**  
  * Backend queries DB for seen\_ids (Items the user has already liked).  
* **Step 1: Graph-Based (Personalized)**  
  * Backend asks C++ Engine for neighbors' interests using BFS.  
  * **Condition**: Returns results if neighbors exist and have liked items not in seen\_ids.  
  * **Scoring**: Items are ranked by **Frequency** \+ **Time Decay** (Recency).  
* **Step 2: Global Trending (Fallback A)**  
  * *Triggered if Step 1 returns empty.*  
  * Backend queries DB for items with the highest global interaction count.  
  * Filters out seen\_ids.  
* **Step 3: New Arrivals (Fallback B)**  
  * *Triggered if Step 2 returns empty (System Cold Start).*  
  * Backend returns the default catalog list.  
  * Filters out seen\_ids.

## **Core Algorithms**

### **1\. Breadth-First Search (BFS)**

Traverses the bipartite graph to find User \-\> Item \-\> Neighbor \-\> Candidate Item.

* **Depth**: 2 (User to Candidate).  
* **Constraint**: Never traverse back to the source user.

### **2\. Time-Decay Scoring**

To ensure recommendations stay fresh, the score of a candidate item is weighted by the age of the neighbor's interaction:

$$ Score(i) \= \\sum\_{n \\in Neighbors} \\frac{1}{1 \+ \\alpha \\cdot \\Delta t} $$

* $\\alpha$: Decay factor (controls how fast items "age").  
* $\\Delta t$: Time elapsed since the interaction occurred.  
* **Effect**: An item liked *today* by a neighbor is worth more than an item liked *last year*.
