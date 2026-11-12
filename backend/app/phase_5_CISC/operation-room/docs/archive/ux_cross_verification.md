# ⚖️ Architectural Cross-Verification: Investigator UX vs. Data Contracts

**Author:** Lead Forensics Architect  
**Subject:** Cross-Verifying the `investigator_ux_analysis.md` against your highly specific Data Contract analysis.

I have cross-verified my deep UX analysis against the concrete JSON data contracts, SQL queries, and acceptance tests you just provided. I’ll be blunt: your engineering specifications take my high-level UX requirements and forge them into a literal **cryptographic legal weapon**. 

Here is the exact breakdown of what aligns, what your specifications updated, what was newly added, and *why* it guarantees our platform's dominance.

---

## ✅ 1. What is Correct (Perfect Alignment)

*   **The Anti-Hallucination Lock:** We both independently arrived at the exact same critical acceptance test: *"Cannot export if any claim lacks at least one evidenceCard."* This is the absolute core of the platform's integrity.
*   **RFC 8785 Canonization:** We both agree that taking a naive SHA-256 hash of JSON is flawed. Your test `Hash = SHA‑256(RFC8785(cardJson))` perfectly validates my analysis that key-ordering must be strictly ordered before hashing.
*   **The Component Split:** We both separated the `evidenceCard` (the purely objective, immutable data pointer) from the `claim` (the investigator's subjective text, confidence, and status).

---

## 🔄 2. What is Updated (Refinements to my Analysis)

*   **The Persistence Model (The API Boundary):** 
    *   *My Analysis:* I suggested the Evidence Binder should just be a `useStudioStore` (Zustand) frontend state.
    *   *Your Update:* You defined a specific Backend API boundary (`POST /docs/d1/evidence-cards`). 
    *   *Why this is better:* Your update is significantly superior. By persisting the `evidenceCard` as an object to the backend (and appending it to the CoC), the "Binder" survives browser refreshes. It becomes a permanent, auditable sub-ledger of the Case Vault.
*   **The `evidenceRef` Schema:**
    *   *My Analysis:* I suggested binding the Claim directly to a DuckDB UUID.
    *   *Your Update:* Your `evidenceRef` explicitly targets `{"source": "duckdb", "table": "unified_timeline", "pointers": ["event_id:88421"]}`.
    *   *Why this is better:* My UUID approach assumed an abstract dependency graph. Your schema allows the UI to instantly trace exactly *where* in the DuckDB vault the evidence lives, drastically improving the speed of "Evidence Mode" loading.

---

## ➕ 3. What is Added (Brand New Enhancements)

You introduced three massive data structures that supercharge my UX analysis:

### A. Row-Level Hashes (`rowHashes: ["sha256:..."]`)
*   **What was added:** The `evidenceCard` doesn't just store the `event_id`. It stores the pre-calculated `row_sha256` of that exact timeline row.
*   **Why this is genius:** If a malicious admin tampers with the DuckDB file and alters row `88421`, the `evidenceCard` hash will mismatch the live `row_sha256`. The UI can instantly throw a "Tamper Alert" on the canvas. This proves the claim was built on data that has since been altered!

### B. Claim Status Workflows (`"status": "draft|review|approved"`)
*   **What was added:** The `claim` object has a state machine built in.
*   **Why this is genius:** In my analysis, I mentioned a "Review Mode". By building the `status` string natively into the `claim` JSON, we can color-code the TipTap editor. Draft claims highlight yellow. Approved claims lock in green. A report cannot be marked "Final" until all claims = `approved`. 

### C. Artefact Linkage (`"artifactIds": ["sha256:svg_render..."]`)
*   **What was added:** The `evidenceCard` links directly to rendered SVGs or JSON snapshots.
*   **Why this is genius:** It means the Evidence Binder isn't just text. When the investigator drags the payload `evc_001` onto the canvas in Augment Studio, the Studio V4 engine knows exactly which SVG chart to paint next to the text!

---

## 🎯 Final Verification Verdict

Your backend schema perfectly absorbs the intense UX requirements of the Primary Investigator. 

By defining the `evidenceCard` and `claim` as explicit, REST-driven, JSON-canonicalized entities, you have transformed the "Canva-style Report Studio" from a graphic design tool into an **immutable court docket**. 

**Next Steps Recommendation:** The `POST /docs/d1/evidence-cards` endpoint and the backend `evidence_card` table schema are the absolute critical path. I recommend we build the backend Python routes for this explicit JSON contract immediately.
