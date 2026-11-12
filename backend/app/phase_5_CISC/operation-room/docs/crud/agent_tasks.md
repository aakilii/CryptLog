# CRUD Agent Tasks — AI Summarisation & Q&A Design

## Integration with Existing AI Agent

The CRUD module extends the Correlation & RCA agent layer. The existing `chat_with_agent()` function already has access to the full case graph — CRUD results enrich this context.

### Current AI Flow (Correlation Chat)
```
Investigator question
    → Gather context (graph nodes + edges)
    → Send to LLM (Ollama/Gemini)
    → Log to agent_chat_logs
    → Return response
```

### Extended Flow (with CRUD)
```
Investigator question
    → Gather context:
        1. Graph nodes + edges (from correlation)
        2. CRUD summary matrix (from crud_summary)
        3. High-risk events (from crud_events WHERE is_high_risk)
    → Build enriched prompt with CRUD patterns
    → Send to LLM
    → Log to agent_chat_logs
    → Return response
```

## AI Summarisation Templates

### Template 1: CRUD Activity Summary
```
User {actor} performed {count} {crud_type} operations on {target}:
- Sensitivity: {max_sensitivity}
- Volume: {total_bytes} bytes
- Time range: {first_seen} to {last_seen}
- {high_risk_count} operations flagged as high-risk
- Average anomaly score: {avg_anomaly}
```

### Template 2: Investigator Alert
```
⚠ ALERT: {actor} performed bulk {crud_type} on {sensitivity} data
- Target: {target_object}
- Time: {normalised_ts} (outside business hours)
- Risk: {risk_reason}
- Recommendation: {recommendation}
```

### Template 3: Cross-Module Correlation
```
🔗 Cross-Module Finding:
1. Anomaly Detection flagged {actor} (score: {anomaly_score})
2. CRUD Analysis shows {count} {crud_type} operations on {target}
3. Correlation Graph links {actor} to {connected_entities}
4. MITRE ATT&CK: {tactic}
```

## Example Q&A

| Question | AI Response Approach |
|----------|---------------------|
| "What did user jdoe do?" | Query crud_summary for actor=jdoe, summarise CRUD breakdown |
| "Show me all deletes on customer data" | Filter crud_events for crud_type=DELETE, sensitivity=HIGH |
| "Who accessed payroll data?" | Query crud_summary for target LIKE '%payroll%' |
| "Why is this user flagged?" | Combine anomaly_scores + crud high-risk + correlation severity |

## Auditability

All AI interactions are logged in `agent_chat_logs`:
```json
{
  "log_id": "uuid",
  "case_id": "CASE-FORENSIC-001",
  "user_query": "What did user jdoe do?",
  "agent_response": "User jdoe performed 47 operations...",
  "llm_provider": "ollama",
  "context_used": {"nodes": 45, "edges": 120, "crud_summaries": 12}
}
```
