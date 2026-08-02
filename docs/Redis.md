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

Redis Cluster routes by hash slot. Multi-key ops must share a **hash tag** `{...}`.

| Key pattern | Slot affinity | Purpose |
|-------------|---------------|---------|
| `qf:deny:{jti}` | by **JTI** | Access denylist entry |
| `qf:{sub}:rt:{jti}` | by **subject** | Refresh session payload |
| `qf:{sub}:rts` | by **subject** | SET of active refresh JTIs |
| `qf:rtidx:{jti}` | by JTI (no tag needed) | JTI → subject reverse index |

- Denylist lookups are **O(1)** and naturally spread across slots by JTI.
- Per-user refresh revoke uses subject-tagged keys in one pipeline (same slot).
- Reverse index is a single-key read before subject-scoped deletes.

## Local cluster overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.redis-cluster.yml up -d

# Initialize cluster once
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
| `POST /auth/logout` | `SET` denylist key for access JTI (TTL = remaining exp) |
| `POST /auth/logout-all` | Deny access JTI + delete all subject refresh keys |
| `validate_access_token` / ForwardAuth verify | `EXISTS` on denylist key |

## Operational notes

- Prefer **non-transactional** pipelines (`transaction=False`) under cluster.
- Do not MULTI/EXEC across keys without identical hash tags.
- Managed Redis (ElastiCache, Memorystore, Azure Cache) in cluster mode works with the same client path.
- Keep `REDIS_KEY_PREFIX` short; change only with a planned key migration.
