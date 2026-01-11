# **Complexity Analysis**

## **1\. Recommendation Latency**

| Strategy | Time Complexity | Typical Latency |
| :---- | :---- | :---- |
| **Redis Cache** | $O(1)$ | \< 1 ms |
| **Weighted BFS** | $O(H\_{user} \\times P\_{item} \\times H\_{neighbor})$ | 2-10 ms |
| **PageRank** | $O(N\_{walks} \\times D\_{depth})$ | 15-50 ms |
| **SQL Fallback** | $O(\\log N)$ (Index Scan) | 50-100 ms |

## **2\. Startup Time (Cold Boot)**

| Method | Complexity | 1 Million Edges |
| :---- | :---- | :---- |
| **SQL Rebuild** | $O(E)$ (Network \+ Parsing) | \~20 seconds |
| **Binary Load** | $O(\\frac{Size}{DiskSpeed})$ | \< 0.2 seconds |

## **3\. Space Complexity**

* **C++ Graph**: $O(V \+ E)$ (Linear w.r.t interactions).  
* **Redis**: $O(U\_{active} \\times K)$ (Stores top K items for active users).
