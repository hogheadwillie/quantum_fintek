# Redis Cluster — control plane reference

Companion to [Redis.md](./Redis.md). Focus: bus, gossip, failure detection, migration, replica validity.

## Ports

| Port | Protocol | Who |
|------|----------|-----|
| `6379` (example) | RESP | Clients + key migration |
| `16379` (client+10000) | Binary cluster bus | Nodes only |

Override bus port with `cluster-port` / `CLUSTER MEET … bus-port`.

## Bus packet sketch

```
[RCmb][totlen][ver][port][type][count]
[currentEpoch][configEpoch][offset]
[sender 40][myslots 2048][slaveof][myip][cport][flags][state][mflags]
[ type-specific body ]
```

Common types: PING=0, PONG=1, MEET=2, FAIL=3, PUBLISH=4, FAILOVER_AUTH_*=5/6, UPDATE=7.

PING/PONG/MEET body = `count` × gossip entries (node id, ip, ports, flags including PFAIL/FAIL).

## Failure detection

```
no PONG > NODE_TIMEOUT     → PFAIL (local)
gossip + majority masters  → FAIL  (broadcast FAIL msg)
valid replica elected      → new master + MOVED
```

Report TTL ≈ `2 × NODE_TIMEOUT`.  
QuantumFintek lab: `NODE_TIMEOUT=5000` ms.

## Replica validity

```
(node-timeout * cluster-slave-validity-factor) + repl-ping-replica-period
```

- factor **0** = always eligible
- factor **10** = default freshness gate
- No effect with `--cluster-replicas 0`

## Slot migration (classic)

1. `SETSLOT IMPORTING` on dest  
2. `SETSLOT MIGRATING` on source  
3. `GETKEYSINSLOT` + `MIGRATE` until empty  
4. `SETSLOT NODE <dest>` on dest, source, (optional) others  

ASK = one-shot; MOVED = permanent map update.

## Client errors (API)

| Error | Meaning |
|-------|---------|
| ConnectionError / TimeoutError | Node unreachable |
| MovedError | Slot map changed; refresh and retry |
| AskError | One-shot redirect during migration |
| ClusterDownError | Uncovered slots / cluster not ok |

## Related files

- `docker-compose.redis-cluster.yml` — 3-node lab overlay
- `apps/api/app/core/redis.py` — standalone / cluster client
- `apps/api/app/core/config.py` — timeouts and node list
