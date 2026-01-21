# **Complexity Analysis**

## **1. Recommendation Latency**

| Strategy | Time Complexity | Typical Latency | Notes |
|----------|---|---|---|
| **Redis Cache Hit** | $O(1)$ | < 1 ms | User has recent recs cached |
| **Weighted BFS** | $O(H_{user} \times P_{item} \times H_{neighbor})$ | 2-10 ms | Depth-2 traversal with genre boost |
| **PageRank (PPR)** | $O(N_{walks} \times D_{depth})$ | 15-50 ms | 10,000 walks × ~3-5 depth |
| **SQL Trending** | $O(\log N)$ (Index Scan) | 50-100 ms | Fallback: aggregation query |
| **JWT Verification** | $O(1)$ | < 1 ms | HMAC-SHA256 signature check |

---

## **2. Startup Time (Cold Boot)**

| Method | Complexity | 1M Edges | Notes |
|--------|---|---|---|
| **SQL Full Rebuild** | $O(E)$ | ~20 sec | Network + parsing all interactions |
| **Binary Snapshot Load** | $O(\frac{\text{Size}}{\text{DiskSpeed}})$ | < 0.2 sec | Disk I/O + memory mapping |
| **Startup Sync** | $O(E)$ | ~2 sec | Verify snapshot + replay fresh SQL rows |

---

## **3. Space Complexity**

| Component | Formula | Example (1M Edges) |
|-----------|---------|---|
| **C++ Graph** | $O(V + E)$ | ~100 MB (nodes + edges) |
| **Binary Snapshot** | $O(V + E)$ | ~80 MB (compressed memory layout) |
| **Redis Cache** | $O(U_{active} \times K)$ | ~10 MB (1000 active users × 5 items each) |
| **SQL Database** | $O(V + E)$ | ~500 MB (Postgres overhead) |

---

## **4. Authentication Overhead**

| Operation | Complexity | Latency |
|-----------|---|---|
| **JWT Decode + Verify** | $O(1)$ | < 1 ms |
| **UUID → user_id Lookup** | $O(1)$ (indexed) | < 1 ms |
| **Ownership Check** | $O(1)$ | < 1 ms |
| **Total Auth Tax** | $O(1)$ | ~2-3 ms per protected endpoint |

---

## **5. Permission Checks**

All writes (`POST /interaction/`, `POST /recommend/preferences`, `POST /auth/register`) include:
1. **JWT Verification**: $O(1)$ HMAC check
2. **Profile Lookup**: $O(\log n)$ indexed query on `profiles.uuid`
3. **Ownership Enforcement**: $O(1)$ comparison (`myId == request.user_id`)
4. **Total**: $O(\log n)$ ≈ 1-2 ms

---

## **6. Cache Invalidation**

| Event | Keys Invalidated | Complexity | Latency |
|-------|---|---|---|
| User likes item | `rec:{user_id}:*` | $O(K)$ (scan + delete) | < 5 ms |
| User updates preferences | `rec:{user_id}:*` | $O(K)$ | < 5 ms |

---

## **7. Profile ID Assignment (New Registrations)**

| Step | Complexity | Notes |
|------|---|---|
| **Collect used IDs** | $O(V)$ | SELECT all profiles.id, user_id |
| **Find smallest gap** | $O(V)$ | Linear scan to find n |
| **Insert profile** | $O(\log V)$ | B-tree insert with PK constraint |
| **Reset sequence** | $O(1)$ | `setval(pg_get_serial_sequence(...))` |
| **Total** | $O(V)$ | ~50 ms for 10K existing users |

---

## **8. Throughput Estimates (per second)**

| Scenario | Throughput | Bottleneck |
|----------|---|---|
| **Cached recommendations** | 10K req/s | Redis throughput |
| **Graph traversal (BFS)** | 100 req/s | C++ compute |
| **PageRank** | 20 req/s | Monte Carlo walks |
| **Like/Unlike** | 500 req/s | Database I/O |
| **Preference update** | 200 req/s | Database I/O + cache invalidation |
