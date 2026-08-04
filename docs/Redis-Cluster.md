# Redis Cluster — control plane reference

Companion to [Redis.md](./Redis.md). Focus: bus, gossip, failure detection, migration, replica validity, and **CLI**.

## Ports

| Port | Protocol | Who |
|------|----------|-----|
| `6379` (example) | RESP | Clients + key migration |
| `16379` (client+10000) | Binary cluster bus | Nodes only |

Override bus port with `cluster-port` / `CLUSTER MEET … bus-port`.

## CLI command reference

All examples assume Docker lab containers `quantum-fintek-redis-1|2|3`.

### Connection

```bash
docker exec -it quantum-fintek-redis-1 redis-cli              # single node
docker exec -it quantum-fintek-redis-1 redis-cli -c           # follow redirects
docker exec -it quantum-fintek-redis-1 redis-cli -c -h redis-node-2 -p 6379
```

### Cluster state

| Command | Purpose |
|---------|---------|
| `CLUSTER INFO` | `cluster_state`, slots ok/pfail/fail, epochs, bus message stats |
| `CLUSTER NODES` | Node ids, flags (master/slave/fail/pfail), slots, link state |
| `CLUSTER SLOTS` | Slot ranges → master (and replicas) |
| `CLUSTER SHARDS` | Redis 7+ shard view |
| `CLUSTER MYID` | This node’s id |
| `CLUSTER MEET host port [bus-port]` | Join node into cluster |
| `CLUSTER FORGET node-id` | Drop a node from the table |
| `CLUSTER REPLICAS master-id` | List replicas of a master |
| `CLUSTER COUNT-FAILURE-REPORTS node-id` | Active PFAIL reports toward FAIL |
| `CLUSTER KEYSLOT key` | Slot for a key (hash tags honored) |
| `CLUSTER COUNTKEYSINSLOT slot` | Key count in slot |
| `CLUSTER GETKEYSINSLOT slot count` | Sample keys in slot |

```bash
docker exec quantum-fintek-redis-1 redis-cli CLUSTER INFO
docker exec quantum-fintek-redis-1 redis-cli CLUSTER NODES
docker exec quantum-fintek-redis-1 redis-cli CLUSTER COUNT-FAILURE-REPORTS <node-id>
docker exec quantum-fintek-redis-1 redis-cli CLUSTER KEYSLOT 'qf:deny:{abc}'
```

### Config

```bash
CONFIG GET cluster-node-timeout
CONFIG GET cluster-require-full-coverage
CONFIG GET cluster-slave-validity-factor
CONFIG GET cluster-replica-validity-factor
CONFIG SET cluster-node-timeout 5000
```

### redis-cli --cluster helpers

```bash
redis-cli --cluster create h1:6379 h2:6379 h3:6379 --cluster-replicas 0 --cluster-yes
redis-cli --cluster check h1:6379
redis-cli --cluster info h1:6379
redis-cli --cluster reshard h1:6379
redis-cli --cluster rebalance h1:6379
redis-cli --cluster fix h1:6379
```

Via Docker:

```bash
docker exec -it quantum-fintek-redis-1 redis-cli --cluster check redis-node-1:6379
docker exec -it quantum-fintek-redis-1 redis-cli --cluster reshard redis-node-1:6379
```

### Slot migration (manual)

```bash
CLUSTER SETSLOT <slot> IMPORTING <source-id>    # on destination
CLUSTER SETSLOT <slot> MIGRATING <dest-id>      # on source
CLUSTER GETKEYSINSLOT <slot> <count>
MIGRATE <dest-host> <dest-port> "" 0 <ms> KEYS k1 k2 ...
CLUSTER SETSLOT <slot> NODE <dest-id>           # dest, then source
CLUSTER SETSLOT <slot> STABLE                   # clear import/migrate flags
```

### Failover (replica required)

```bash
CLUSTER FAILOVER              # coordinated when possible
CLUSTER FAILOVER FORCE        # primary unreachable; still needs majority
CLUSTER FAILOVER TAKEOVER     # unilateral — use with care
```

### App keys (examples)

```bash
redis-cli -c EXISTS 'qf:deny:{jti}'
redis-cli -c TTL 'qf:deny:{jti}'
redis-cli -c SMEMBERS 'qf:{user-id}:rts'
redis-cli -c GET 'qf:rtidx:{jti}'
```

## Bus packet sketch

```
[RCmb][totlen][ver][port][type][count]
[currentEpoch][configEpoch][offset]
[sender 40][myslots 2048][slaveof][myip][cport][flags][state][mflags]
[ type-specific body ]
```

Common types: PING=0, PONG=1, MEET=2, FAIL=3, PUBLISH=4, FAILOVER_AUTH_*=5/6, UPDATE=7.

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
- [Redis.md](./Redis.md) — app keys, timeouts, full CLI quick reference
