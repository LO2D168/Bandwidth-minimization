from collections import deque


def find_upperbound(n, adj):
    label = [-1] * (n + 1)
    visited = [False] * (n + 1)
    idx = 0

    vertices = sorted(range(1, n + 1), key=lambda v: len(adj[v]))

    for u in vertices:
        if visited[u]:
            continue

        q = deque([u])
        visited[u] = True

        while q:
            cur = q.popleft()
            idx += 1
            label[cur] = idx

            nxt = [v for v in adj[cur] if not visited[v]]
            nxt.sort(key=lambda v: len(adj[v]))

            for v in nxt:
                if not visited[v]:
                    visited[v] = True
                    q.append(v)

    bandwidth = 0
    for u in range(1, n + 1):
        for v in adj[u]:
            bandwidth = max(bandwidth, abs(label[u] - label[v]))

    return bandwidth


def find_lowerbound(n, adj):
    if n == 0:
        return 0
    return max(len(adj[v]) for v in range(1, n + 1)) // 2
