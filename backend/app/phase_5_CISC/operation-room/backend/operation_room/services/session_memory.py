"""
Session Memory Service - Oracle 26AI Phase 3.

Phase-aware conversation memory with TTL management:
- Store conversation turns with embeddings
- Phase awareness (discovery, analysis, reporting)
- TTL-based memory pruning
- Context window management
- Integration with chat service
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from operation_room.database import open_vault
from operation_room.services.vector_store import get_vector_store, CollectionType, SearchResult
from operation_room.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class InvestigationPhase(str, Enum):
    """Investigation phases for context management."""
    DISCOVERY = "discovery"      # Initial data exploration
    ANALYSIS = "analysis"        # Deep analysis, anomaly detection
    CORRELATION = "correlation"  # Cross-module correlation
    HYPOTHESIS = "hypothesis"    # Hypothesis formation
    VALIDATION = "validation"    # Evidence validation
    REPORTING = "reporting"      # Report generation
    REVIEW = "review"           # Final review and approval


@dataclass
class MemoryTurn:
    """A single conversation turn in memory."""
    turn_id: str
    session_id: str
    case_id: str
    role: str  # user, assistant, system
    content: str
    phase: InvestigationPhase
    timestamp: datetime
    token_count: int = 0
    embedding_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl_hours: int = 24  # Time-to-live


@dataclass
class SessionContext:
    """Aggregated context for a session."""
    session_id: str
    case_id: str
    current_phase: InvestigationPhase
    total_turns: int
    total_tokens: int
    key_topics: List[str]
    active_hypotheses: List[str]
    last_activity: datetime


class SessionMemory:
    """
    Phase-aware session memory with TTL management.
    
    Features:
    - Store conversation turns with vector embeddings
    - Phase-based context weighting
    - TTL-based automatic pruning
    - Semantic retrieval of relevant past context
    - Token budget management
    """
    
    # Phase importance weights for context retrieval
    PHASE_WEIGHTS = {
        InvestigationPhase.DISCOVERY: 0.6,
        InvestigationPhase.ANALYSIS: 0.8,
        InvestigationPhase.CORRELATION: 0.9,
        InvestigationPhase.HYPOTHESIS: 1.0,
        InvestigationPhase.VALIDATION: 0.95,
        InvestigationPhase.REPORTING: 0.85,
        InvestigationPhase.REVIEW: 0.7,
    }
    
    # Default TTL by phase (hours)
    PHASE_TTL = {
        InvestigationPhase.DISCOVERY: 12,
        InvestigationPhase.ANALYSIS: 24,
        InvestigationPhase.CORRELATION: 24,
        InvestigationPhase.HYPOTHESIS: 48,
        InvestigationPhase.VALIDATION: 36,
        InvestigationPhase.REPORTING: 72,
        InvestigationPhase.REVIEW: 48,
    }
    
    def __init__(self, case_id: str, session_id: Optional[str] = None):
        self.case_id = case_id
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self._vector_store = get_vector_store()
        self._embedding_service = get_embedding_service()
        self._current_phase = InvestigationPhase.DISCOVERY
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create session memory tables."""
        conn = open_vault(self.case_id)
        try:
            # Session memory turns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    turn_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    case_id VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    content TEXT NOT NULL,
                    phase VARCHAR NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    token_count INTEGER DEFAULT 0,
                    embedding_id VARCHAR,
                    ttl_hours INTEGER DEFAULT 24,
                    expires_at TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Session state tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    current_phase VARCHAR DEFAULT 'discovery',
                    total_turns INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    key_topics JSON,
                    active_hypotheses JSON,
                    metadata JSON
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_memory_session 
                ON session_memory(session_id, timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_memory_expires 
                ON session_memory(expires_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_state_case 
                ON session_state(case_id)
            """)
            
        finally:
            conn.close()
    
    def add_turn(
        self,
        role: str,
        content: str,
        phase: Optional[InvestigationPhase] = None,
        token_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: Optional[int] = None
    ) -> str:
        """
        Add a conversation turn to memory.
        
        Args:
            role: Turn role (user, assistant, system)
            content: Turn content
            phase: Investigation phase (uses current if not provided)
            token_count: Estimated token count
            metadata: Additional metadata
            ttl_hours: Custom TTL (uses phase default if not provided)
            
        Returns:
            Turn ID
        """
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        phase = phase or self._current_phase
        ttl = ttl_hours or self.PHASE_TTL.get(phase, 24)
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl)
        
        meta = metadata or {}
        meta['phase'] = phase.value
        
        # Add to vector store for semantic retrieval
        embedding_id = None
        if len(content) > 50:  # Only embed substantial content
            try:
                embedding_id = self._vector_store.add_document(
                    collection_type=CollectionType.SESSION,
                    content=content,
                    metadata={'role': role, 'session_id': self.session_id, **meta},
                    doc_id=turn_id,
                    case_id=self.case_id
                )
            except Exception as e:
                logger.warning(f"Failed to add turn to vector store: {e}")
        
        # Add to SQL
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO session_memory (
                    turn_id, session_id, case_id, role, content, phase,
                    timestamp, token_count, embedding_id, ttl_hours, expires_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                turn_id, self.session_id, self.case_id, role, content,
                phase.value, now, token_count, embedding_id, ttl, expires_at,
                json.dumps(meta)
            ])
            
            # Update session state
            self._update_session_state(token_count, content)
            
        finally:
            conn.close()
        
        logger.debug(f"Added turn {turn_id} to session {self.session_id}")
        return turn_id
    
    def _update_session_state(self, tokens: int, content: str) -> None:
        """Update session state with new turn."""
        conn = open_vault(self.case_id)
        try:
            # Upsert session state
            conn.execute("""
                INSERT INTO session_state (
                    session_id, case_id, current_phase, total_turns, total_tokens,
                    last_activity, key_topics, active_hypotheses
                ) VALUES (?, ?, ?, 1, ?, now(), '[]', '[]')
                ON CONFLICT(session_id) DO UPDATE SET
                    current_phase = ?,
                    total_turns = total_turns + 1,
                    total_tokens = total_tokens + ?,
                    last_activity = now()
            """, [
                self.session_id, self.case_id, self._current_phase.value, tokens,
                self._current_phase.value, tokens
            ])
        finally:
            conn.close()
    
    def get_recent_turns(
        self,
        n_turns: int = 10,
        phase_filter: Optional[InvestigationPhase] = None,
        include_expired: bool = False
    ) -> List[MemoryTurn]:
        """
        Get recent conversation turns.
        
        Args:
            n_turns: Maximum turns to return
            phase_filter: Filter to specific phase
            include_expired: Include expired turns
            
        Returns:
            List of memory turns (newest first)
        """
        conn = open_vault(self.case_id)
        try:
            conditions = ["session_id = ?"]
            params = [self.session_id]
            
            if phase_filter:
                conditions.append("phase = ?")
                params.append(phase_filter.value)
            
            if not include_expired:
                conditions.append("expires_at > CURRENT_TIMESTAMP")
            
            where_clause = " AND ".join(conditions)
            
            rows = conn.execute(f"""
                SELECT turn_id, session_id, case_id, role, content, phase,
                       timestamp, token_count, embedding_id, ttl_hours, metadata
                FROM session_memory
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [n_turns]).fetchall()
            
            return [
                MemoryTurn(
                    turn_id=r[0],
                    session_id=r[1],
                    case_id=r[2],
                    role=r[3],
                    content=r[4],
                    phase=InvestigationPhase(r[5]),
                    timestamp=r[6],
                    token_count=r[7],
                    embedding_id=r[8],
                    ttl_hours=r[9],
                    metadata=json.loads(r[10]) if r[10] else {}
                )
                for r in rows
            ]
        finally:
            conn.close()
    
    def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 4000,
        n_semantic: int = 5,
        n_recent: int = 3
    ) -> List[MemoryTurn]:
        """
        Get relevant context for a query.
        
        Combines:
        - Recent turns (recency bias)
        - Semantically similar past turns
        - Phase-weighted importance
        
        Args:
            query: The current query
            max_tokens: Maximum token budget
            n_semantic: Number of semantic matches to consider
            n_recent: Number of recent turns to always include
            
        Returns:
            List of memory turns within token budget
        """
        # Get recent turns (always include)
        recent = self.get_recent_turns(n_turns=n_recent)
        recent_ids = {t.turn_id for t in recent}
        
        # Semantic search for relevant context
        semantic_results = self._search_semantic(query, n_results=n_semantic + n_recent)
        
        # Combine and deduplicate
        candidates = list(recent)
        
        for result in semantic_results:
            if result.id not in recent_ids:
                # Get full turn data
                turn = self._get_turn_by_id(result.id)
                if turn:
                    # Apply phase weight to score
                    phase_weight = self.PHASE_WEIGHTS.get(turn.phase, 0.5)
                    turn.metadata['relevance_score'] = result.score * phase_weight
                    candidates.append(turn)
        
        # Sort by weighted relevance (recent turns get boost)
        for i, turn in enumerate(candidates[:n_recent]):
            turn.metadata['relevance_score'] = turn.metadata.get('relevance_score', 0) + 0.2
        
        candidates.sort(
            key=lambda t: t.metadata.get('relevance_score', 0),
            reverse=True
        )
        
        # Fit within token budget
        result = []
        token_count = 0
        
        for turn in candidates:
            if token_count + turn.token_count <= max_tokens:
                result.append(turn)
                token_count += turn.token_count
        
        # Sort by timestamp for natural order
        result.sort(key=lambda t: t.timestamp)
        
        return result
    
    def _search_semantic(self, query: str, n_results: int = 10) -> List[SearchResult]:
        """Search session memory semantically."""
        try:
            return self._vector_store.search(
                collection_type=CollectionType.SESSION,
                query=query,
                case_id=self.case_id,
                n_results=n_results,
                where={'session_id': self.session_id}
            )
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return []
    
    def _get_turn_by_id(self, turn_id: str) -> Optional[MemoryTurn]:
        """Get a specific turn by ID."""
        conn = open_vault(self.case_id)
        try:
            row = conn.execute("""
                SELECT turn_id, session_id, case_id, role, content, phase,
                       timestamp, token_count, embedding_id, ttl_hours, metadata
                FROM session_memory
                WHERE turn_id = ?
            """, [turn_id]).fetchone()
            
            if not row:
                return None
            
            return MemoryTurn(
                turn_id=row[0],
                session_id=row[1],
                case_id=row[2],
                role=row[3],
                content=row[4],
                phase=InvestigationPhase(row[5]),
                timestamp=row[6],
                token_count=row[7],
                embedding_id=row[8],
                ttl_hours=row[9],
                metadata=json.loads(row[10]) if row[10] else {}
            )
        finally:
            conn.close()
    
    def set_phase(self, phase: InvestigationPhase) -> None:
        """Set the current investigation phase."""
        self._current_phase = phase
        
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                UPDATE session_state
                SET current_phase = ?, last_activity = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, [phase.value, self.session_id])
        finally:
            conn.close()
        
        logger.info(f"Session {self.session_id} phase changed to {phase.value}")
    
    def get_session_context(self) -> Optional[SessionContext]:
        """Get aggregated session context."""
        conn = open_vault(self.case_id)
        try:
            row = conn.execute("""
                SELECT session_id, case_id, current_phase, total_turns,
                       total_tokens, key_topics, active_hypotheses, last_activity
                FROM session_state
                WHERE session_id = ?
            """, [self.session_id]).fetchone()
            
            if not row:
                return None
            
            return SessionContext(
                session_id=row[0],
                case_id=row[1],
                current_phase=InvestigationPhase(row[2]) if row[2] else InvestigationPhase.DISCOVERY,
                total_turns=row[3] or 0,
                total_tokens=row[4] or 0,
                key_topics=json.loads(row[5]) if row[5] else [],
                active_hypotheses=json.loads(row[6]) if row[6] else [],
                last_activity=row[7]
            )
        finally:
            conn.close()
    
    def prune_expired(self) -> int:
        """Remove expired turns."""
        conn = open_vault(self.case_id)
        try:
            # Get IDs to delete from vector store
            expired_ids = conn.execute("""
                SELECT embedding_id FROM session_memory
                WHERE expires_at < CURRENT_TIMESTAMP AND embedding_id IS NOT NULL
            """).fetchall()
            
            # Delete from SQL
            result = conn.execute("""
                DELETE FROM session_memory
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            deleted_count = result.rowcount if hasattr(result, 'rowcount') else 0
            
            # Delete from vector store
            if expired_ids:
                try:
                    self._vector_store.delete(
                        CollectionType.SESSION,
                        [r[0] for r in expired_ids if r[0]],
                        case_id=self.case_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete from vector store: {e}")
            
            logger.info(f"Pruned {deleted_count} expired turns from session memory")
            return deleted_count
            
        finally:
            conn.close()
    
    def summarize_session(self, max_length: int = 500) -> str:
        """Generate a summary of the session."""
        turns = self.get_recent_turns(n_turns=20)
        
        if not turns:
            return "No conversation history."
        
        # Extract key content
        user_messages = [t.content for t in turns if t.role == 'user']
        assistant_messages = [t.content for t in turns if t.role == 'assistant']
        
        # Build summary
        summary_parts = []
        summary_parts.append(f"Session: {self.session_id}")
        summary_parts.append(f"Phase: {self._current_phase.value}")
        summary_parts.append(f"Turns: {len(turns)}")
        
        if user_messages:
            recent_query = user_messages[-1][:100]
            summary_parts.append(f"Recent query: {recent_query}...")
        
        return " | ".join(summary_parts)[:max_length]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session memory statistics."""
        conn = open_vault(self.case_id)
        try:
            # Total turns
            total = conn.execute("""
                SELECT COUNT(*), SUM(token_count)
                FROM session_memory
                WHERE session_id = ?
            """, [self.session_id]).fetchone()
            
            # By phase
            by_phase = conn.execute("""
                SELECT phase, COUNT(*) as count
                FROM session_memory
                WHERE session_id = ?
                GROUP BY phase
            """, [self.session_id]).fetchall()
            
            # Expired
            expired = conn.execute("""
                SELECT COUNT(*)
                FROM session_memory
                WHERE session_id = ? AND expires_at < CURRENT_TIMESTAMP
            """, [self.session_id]).fetchone()
            
            return {
                'session_id': self.session_id,
                'total_turns': total[0] or 0,
                'total_tokens': total[1] or 0,
                'current_phase': self._current_phase.value,
                'by_phase': [{'phase': r[0], 'count': r[1]} for r in by_phase],
                'expired_turns': expired[0] or 0
            }
        finally:
            conn.close()


# Global registry
_session_memories: Dict[str, SessionMemory] = {}


def get_session_memory(case_id: str, session_id: Optional[str] = None) -> SessionMemory:
    """Get or create session memory."""
    key = f"{case_id}:{session_id}" if session_id else case_id
    if key not in _session_memories:
        _session_memories[key] = SessionMemory(case_id, session_id)
    return _session_memories[key]
