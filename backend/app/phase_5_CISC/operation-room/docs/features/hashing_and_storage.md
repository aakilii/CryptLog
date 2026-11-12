# Hashing & Storage — Design Specification

## Purpose

Ensure every evidence artefact is cryptographically hashed at import time so its integrity can be verified at any future point. This is the cornerstone of forensic admissibility.

---

## Hashing Strategy

### Algorithm

| Algorithm | Status  | Notes                                      |
|-----------|---------|--------------------------------------------|
| SHA-256   | Default | Industry standard; NIST-approved; fast     |
| SHA-512   | Supported | Higher security margin                   |
| BLAKE2b   | Supported | Fastest; collision-resistant               |

Configurable via `OPROOM_HASH_ALGORITHM` env variable.

### What Is Hashed

- **Per-batch hash:** The entire JSON result set from the NLP agent, serialised with sorted keys and no whitespace (`json.dumps(records, sort_keys=True, separators=(',', ':'))`). This produces a deterministic canonical form.
- **Per-batch size:** The byte length of the canonical JSON payload is also recorded.

### Determinism

Hashing uses canonical JSON serialisation. Given the same input records in any order, the sorted-keys serialisation produces the same bytes and therefore the same hash.

## Storage Architecture

```
data/
└── cases/
    └── {case_id}/
        └── vault.duckdb        ← Single DuckDB file per case
```

### DuckDB Tables

| Table              | Mutability     | Purpose                            |
|--------------------|----------------|------------------------------------|
| case_metadata      | Read/Update    | Case info (no evidence data)       |
| scope_definition   | Append-only    | Scope entries                      |
| raw_events         | Append-only    | Imported log records               |
| evidence_hashes    | Append-only    | Hash records for each import batch |
| chain_of_custody   | Append-only    | Audit trail                        |

### Immutability Enforcement

- `raw_events` and `evidence_hashes` are **append-only** — the application layer never issues UPDATE or DELETE against them.
- DuckDB doesn't natively enforce append-only constraints; the restriction is enforced by the service layer.
- Future enhancement: write-ahead verification using the global audit log HMAC chain.

## Integrity Verification

```
POST /api/cases/{id}/evidence/verify
Body: { "hash_id": "..." }
```

1. Reads the stored hash from `evidence_hashes`
2. Re-reads all `raw_events` for the case
3. Recomputes the hash using the same algorithm
4. Compares and returns match/mismatch
5. Records a `VERIFY_HASH` CoC event with both hashes

## Forensic References

- **NIST SP 800-86** §4.2.2 — Hashing for integrity verification
- **SWGDE Best Practices** — "Hash values should be generated using validated algorithms"
- **ISO/IEC 27037** §7.2 — Preservation of digital evidence integrity
