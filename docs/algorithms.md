# **Recommendation Algorithms**

## **1. Weighted Breadth-First Search (BFS)**

* **Type**: Deterministic / Local  
* **Logic**: Finds items liked by immediate neighbors (Depth-2).  
* **Scoring**:
Score = $\sum (1 + \text{GenreBoost}) \times \frac{1}{1 + \alpha \Delta t}$  
* **Use Case**: Best for explaining "Why" (e.g., "Because you liked X").  

---  

## **2. Personalized PageRank (PPR)**

* **Type**: Probabilistic / Global  
* **Logic**: Uses **Monte Carlo Simulation**.  
  1. Start a "Walker" at the Target User node.  
  2. Randomly traverse User \-\> Item \-\> User \-\> Item.  
  3. Repeat $N$ times (Default: 10,000 walks).  
  4. Count visit frequency for every item.  
* **Use Case**: Better at finding "hidden" connections and popular communities beyond immediate neighbors.  

---  
  
## **3. Genre-Aware Boosting**

* **Type**: Dynamic Scoring Modifier  
* **Logic**: When a user selects genre preferences (e.g., "Action", "Sci-Fi"), the algorithm dynamically increases edge weights for items in those categories:
$$\text{GenreBoost} = \begin{cases} 0.5 & \text{if item category } \in \text{ user preferences} \\ 0 & \text{otherwise} \end{cases}$$
* **Use Case**: Personalizes both BFS and PageRank traversals. Preferences are loaded on login and cached for the session.  

---  
  
## **4. Global Trending (Fallback)**

* **Type**: Deterministic / Aggregate  
* **Logic**: * **Logic**: Uses SQL aggregation to find the most popular items across the entire dataset.

```sql
SELECT item_id
FROM interactions
GROUP BY item_id
ORDER BY COUNT(*) DESC;
```  

* **Use Case**: Triggered when graph algorithms return empty results (e.g., "Cold Start" for new users with no history or neighbors).  

---  
  
## **5. Catalog Default (Final Fallback)**
* **Type**: Sequential / Deterministic
* **Logic**: Returns items in order from the catalog (by item ID).
* **Use Case**: Last resort when both graph and trending are empty (rare). Guarantees a response.  

---  
  
## **6. Binary Graph Serialization**

Instead of rebuilding the graph row-by-row from SQL ($O(E)$), we serialize the C++ memory layout directly to disk.

* **Write**: Iterates std::unordered\_map buckets and writes raw bytes to fstream.  
* **Read**: Allocates memory and reads raw bytes directly into containers.
* **Benefit**: Startup time becomes independent of interaction count (~100ms vs ~20s).  

---  
  
## **7. Cache-Aside Pattern (Redis)**  
* **Logic**: Check Redis for rec:{user_id}:{algo}:{k}. If hit, return instantly. On miss, compute, then write back with 1-hour TTL.
* **Invalidation**: Cache keys are deleted when a user likes/dislikes an item or updates genre preferences.
* **Benefit**: Hot users see sub-millisecond response times.
