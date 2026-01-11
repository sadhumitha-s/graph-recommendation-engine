# **Recommendation Algorithms**

## **1\. Weighted Breadth-First Search (BFS)**

* **Type**: Deterministic / Local  
* **Logic**: Finds items liked by immediate neighbors (Depth-2).  
* **Scoring**:
Score = $\sum (1 + \text{GenreBoost}) \times \frac{1}{1 + \alpha \Delta t}$  
* **Use Case**: Best for explaining "Why" (e.g., "Because you liked X").

## **2\. Personalized PageRank (PPR)**

* **Type**: Probabilistic / Global  
* **Logic**: Uses **Monte Carlo Simulation**.  
  1. Start a "Walker" at the Target User node.  
  2. Randomly traverse User \-\> Item \-\> User \-\> Item.  
  3. Repeat $N$ times (Default: 10,000 walks).  
  4. Count visit frequency for every item.  
* **Use Case**: Better at finding "hidden" connections and popular communities beyond immediate neighbors.

## **3\. Global Trending (Fallback)**

* **Type**: Deterministic / Aggregate  
* **Logic**: * **Logic**: Uses SQL aggregation to find the most popular items across the entire dataset.

```sql
SELECT item_id
FROM interactions
GROUP BY item_id
ORDER BY COUNT(*) DESC;
```  

* **Use Case**: Triggered when graph algorithms return empty results (e.g., "Cold Start" for new users with no history or neighbors).

## **4\. Binary Graph Serialization**

Instead of rebuilding the graph row-by-row from SQL ($O(E)$), we serialize the C++ memory layout directly to disk.

* **Write**: Iterates std::unordered\_map buckets and writes raw bytes to fstream.  
* **Read**: Allocates memory and reads raw bytes directly into containers.
