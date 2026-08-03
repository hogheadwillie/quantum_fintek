# Redis — sessions & denylist sharding

QuantumFintek uses Redis for:

1. **Access-token denylist** (`logout` / `logout-all`)
2. **Refresh-token store** (rotation + revoke)

## Modes

| Mode | Config |
|------|--------|
| Standalone (default) | `REDIS_MODE=standalone` + `REDIS_URL=redis://redis:6379/0` |
| Cluster | `REDIS_MODE=cluster` + `REDIS_CLUSTER_NODES=host1:6379,host2:6379,...` |

## Cluster key design (hash tags)

| Key pattern | Slot affinity | Purpose |
|-------------|---------------|---------|
| `qf:deny:{jti}` | by **JTI** | Access denylist entry |
| `qf:{sub}:rt:{jti}` | by **subject** | Refresh session payload |
| `qf:{sub}:rts` | by **subject** | SET of active refresh JTIs |
| `qf:rtidx:{jti}` | by JTI | JTI → subject reverse index |

## cluster-node-timeout tuning

Redis default is **15000 ms**. QuantumFintek local cluster overlay uses **5000 ms**.

| Environment | Suggested `REDIS_CLUSTER_NODE_TIMEOUT_MS` | Why |
|-------------|-------------------------------------------|-----|
| Local Docker / same LAN | **5000** | Faster PFAIL→FAIL; RTT is low |
| Single-region production | **10000** | Balance detection vs brief network blips |
| Multi-AZ / higher jitter | **15000** (Redis default) | Avoid false failovers |

### What the timeout controls

- **PFAIL**: peer unreachable longer than `NODE_TIMEOUT`
- **Reconnect attempt**: ~`NODE_TIMEOUT / 2` without PONG
- **FAIL report validity**: ~`NODE_TIMEOUT × 2`
- **Majority loss**: node stops writes after ~`NODE_TIMEOUT` without majority

Approximate detection window (healthy majority, true outage):

```
PFAIL  ≈ NODE_TIMEOUT
FAIL   ≈ NODE_TIMEOUT … 2×NODE_TIMEOUT (gossip majority)
```

With **5000 ms**: expect confirmed FAIL on the order of **~5–10 s**.  
With **15000 ms**: often **~15–30 s**.

### Important: replicas

This repo’s lab cluster is created with `--cluster-replicas 0` (masters only).  
Lowering `cluster-node-timeout` **speeds failure detection** but **does not promote a new master**. Uncovered slots stay down until the node returns. For HA, recreate with replicas ≥ 1 per master.

### Client alignment

| Setting | Default | Role |
|---------|---------|------|
| `REDIS_SOCKET_CONNECT_TIMEOUT` | 2.0 s | Fail fast on dead TCP |
| `REDIS_SOCKET_TIMEOUT` | 5.0 s | Matches 5 s node-timeout scale |
| `REDIS_CLUSTER_ERROR_RETRY_ATTEMPTS` | 5 | Retry after MOVED / blips |

Keep **connect timeout < node-timeout**. Raise socket timeout if commands are large or network is slow.

### Change timeout

```bash
# .env
REDIS_CLUSTER_NODE_TIMEOUT_MS=10000
REDIS_SOCKET_TIMEOUT=8.0
REDIS_CLUSTER_ERROR_RETRY_ATTEMPTS=5
```

Recreate Redis nodes after changing server timeout (config is process startup):

```bash
docker compose -f docker-compose.yml -f docker-compose.redis-cluster.yml up -d --force-recreate redis-node-1 redis-node-2 redis-node-3
```

Verify:

```bash
docker exec quantum-fintek-redis-1 redis-cli CONFIG GET cluster-node-timeout
# should print 5000 (or your override)
```

## Local cluster overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.redis-cluster.yml up -d

docker compose -f docker-compose.redis-cluster.yml exec redis-node-1 \
  redis-cli --cluster create redis-node-1:6379 redis-node-2:6379 redis-node-3:6379 \
  --cluster-replicas 0 --cluster-yes

docker compose -f docker-compose.yml -f docker-compose.redis-cluster.yml up --build api
```

## Application behavior

| API | Redis effect |
|-----|----------------|
| `POST /auth/login` | Store refresh under subject tag; index JTI |
| `POST /auth/refresh` | Revoke old JTI; write new |
| `POST /auth/logout` | Denylist access JTI (TTL = remaining exp) |
| `POST /auth/logout-all` | Deny access JTI + all subject refresh keys |
| `validate_access_token` / ForwardAuth | `EXISTS` on denylist key |

## Operational notes

- Prefer non-transactional pipelines under cluster.
- Do not MULTI/EXEC across keys without identical hash tags.
- Logout denylist is best-effort under partition; JWT `exp` remains the hard bound.
