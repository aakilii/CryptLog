# Case Wizard — Design Specification

## Purpose

The Case Wizard is a 4‑step form that guides investigators through creating a new forensic case. It captures all metadata required to initialise the Case Vault and define the investigation scope.

---

## Steps

### Step 1 — Case Details

| Field              | Type      | Required | Validation                                |
|--------------------|-----------|----------|-------------------------------------------|
| Title              | text      | ✅       | Min 1 char, max 256                       |
| Description        | textarea  | ❌       | Free text                                 |
| Classification     | select    | ✅       | UNCLASSIFIED / CONFIDENTIAL / SECRET / TOP SECRET |
| Priority           | select    | ✅       | LOW / MEDIUM / HIGH / CRITICAL            |
| Investigation Reason | textarea | ❌     | Free text, recorded in CoC                |
| Lead Investigator  | text      | ✅       | Auto-filled from authenticated user       |

### Step 2 — Scope & Suspects

| Field           | Type              | Required | Notes                          |
|-----------------|-------------------|----------|--------------------------------|
| Time Start      | datetime-local    | ✅       | ISO‑8601 timestamp             |
| Time End        | datetime-local    | ✅       | Must be after start            |
| Suspects        | text (CSV)        | ❌       | Comma-separated user/IP list   |
| Target Systems  | text (CSV)        | ❌       | Comma-separated hostnames      |

### Step 3 — Log Sources

Multi‑select checkbox grid. At least one source must be selected:

`AUTH` · `VPN` · `FW` · `DB` · `APP` · `EPP` · `FILE`

### Step 4 — Review & Create

Read-only summary table. On submit the frontend calls:

```
POST /api/cases
```

A scope entry is created for each selected log source with the shared time window and suspects.

---

## Error Handling

- **Validation errors** are shown inline beneath the failing field.
- **API errors** (e.g., vault creation failure) display a toast at the top.
- On success the user is redirected to the case detail page.

## Audit

The backend records a `CASE_CREATED` chain‑of‑custody event with the investigation reason as justification.
