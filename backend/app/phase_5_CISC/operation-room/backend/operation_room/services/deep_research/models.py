"""
Chain-of-Thought Data Models.

Defines the data structures for representing reasoning steps
in the DeepResearch investigation assistant.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ThoughtType(str, Enum):
    """Types of thoughts in the reasoning chain."""
    
    # High-level phases
    PLANNING = "planning"           # Creating investigation plan
    HYPOTHESIS = "hypothesis"       # Formulating hypothesis
    ANALYSIS = "analysis"           # Analyzing evidence
    SYNTHESIS = "synthesis"         # Combining findings
    CONCLUSION = "conclusion"       # Drawing conclusions
    
    # Actions
    QUERY = "query"                 # Querying data/evidence
    VERIFICATION = "verification"  # Verifying findings
    COMPARISON = "comparison"       # Comparing results
    CORRELATION = "correlation"     # Finding correlations
    
    # Communication
    QUESTION = "question"           # Question for human
    CLARIFICATION = "clarification" # Clarification request
    SUMMARY = "summary"             # Summarizing findings
    
    # Evidence
    EVIDENCE_FOUND = "evidence_found"       # Evidence discovered
    EVIDENCE_MISSING = "evidence_missing"   # Expected evidence missing
    EVIDENCE_CONFLICT = "evidence_conflict" # Conflicting evidence


class ThoughtStatus(str, Enum):
    """Status of a thought node."""
    PENDING = "pending"       # Not yet started
    IN_PROGRESS = "in_progress"  # Currently being processed
    COMPLETED = "completed"   # Successfully completed
    FAILED = "failed"         # Failed to complete
    BLOCKED = "blocked"       # Waiting for input/dependency


@dataclass
class ThoughtNode:
    """
    A single node in the chain of thought.
    
    Represents one reasoning step with:
    - Content: The actual thought/reasoning
    - Type: What kind of thought this is
    - Status: Current state
    - Evidence: Supporting evidence references
    - Children: Sub-thoughts for detailed reasoning
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Content
    title: str = ""
    content: str = ""
    thought_type: ThoughtType = ThoughtType.ANALYSIS
    
    # Status
    status: ThoughtStatus = ThoughtStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Relationships
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    
    # Evidence and data
    evidence_refs: List[str] = field(default_factory=list)  # Evidence vault references
    data: Dict[str, Any] = field(default_factory=dict)      # Associated data
    
    # Results
    result: Optional[str] = None
    confidence: Optional[float] = None  # 0.0 to 1.0
    error: Optional[str] = None
    
    # Metadata
    module_source: Optional[str] = None  # Which module generated this
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start(self) -> None:
        """Mark thought as started."""
        self.status = ThoughtStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def complete(self, result: Optional[str] = None, confidence: Optional[float] = None) -> None:
        """Mark thought as completed."""
        self.status = ThoughtStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress = 1.0
        if result:
            self.result = result
        if confidence is not None:
            self.confidence = confidence
    
    def fail(self, error: str) -> None:
        """Mark thought as failed."""
        self.status = ThoughtStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error
    
    def block(self, reason: str) -> None:
        """Mark thought as blocked."""
        self.status = ThoughtStatus.BLOCKED
        self.error = reason
    
    def add_evidence(self, evidence_ref: str) -> None:
        """Add an evidence reference."""
        if evidence_ref not in self.evidence_refs:
            self.evidence_refs.append(evidence_ref)
    
    def duration_ms(self) -> Optional[int]:
        """Get duration in milliseconds if completed."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "thought_type": self.thought_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "evidence_refs": self.evidence_refs,
            "data": self.data,
            "result": self.result,
            "confidence": self.confidence,
            "error": self.error,
            "module_source": self.module_source,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThoughtNode":
        """Create from dictionary."""
        node = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            content=data.get("content", ""),
            thought_type=ThoughtType(data.get("thought_type", "analysis")),
            status=ThoughtStatus(data.get("status", "pending")),
            progress=data.get("progress", 0.0),
            parent_id=data.get("parent_id"),
            children_ids=data.get("children_ids", []),
            evidence_refs=data.get("evidence_refs", []),
            data=data.get("data", {}),
            result=data.get("result"),
            confidence=data.get("confidence"),
            error=data.get("error"),
            module_source=data.get("module_source"),
            metadata=data.get("metadata", {}),
        )
        
        # Parse dates
        if data.get("created_at"):
            node.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            node.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            node.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return node


@dataclass
class ThoughtTree:
    """
    Hierarchical structure of thoughts.
    
    Represents the full reasoning tree with:
    - Root thoughts: Top-level reasoning steps
    - All nodes indexed by ID for quick lookup
    - Navigation and manipulation methods
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    
    # All nodes indexed by ID
    nodes: Dict[str, ThoughtNode] = field(default_factory=dict)
    
    # Root node IDs (no parent)
    root_ids: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_node(
        self,
        node: ThoughtNode,
        parent_id: Optional[str] = None,
    ) -> ThoughtNode:
        """
        Add a node to the tree.
        
        Args:
            node: The thought node to add
            parent_id: Optional parent node ID
            
        Returns:
            The added node
        """
        node.parent_id = parent_id
        self.nodes[node.id] = node
        
        if parent_id:
            # Add as child of parent
            parent = self.nodes.get(parent_id)
            if parent and node.id not in parent.children_ids:
                parent.children_ids.append(node.id)
        else:
            # Add as root
            if node.id not in self.root_ids:
                self.root_ids.append(node.id)
        
        self.updated_at = datetime.now()
        return node
    
    def create_node(
        self,
        title: str,
        content: str = "",
        thought_type: ThoughtType = ThoughtType.ANALYSIS,
        parent_id: Optional[str] = None,
        **kwargs,
    ) -> ThoughtNode:
        """
        Create and add a new node.
        
        Args:
            title: Node title
            content: Node content
            thought_type: Type of thought
            parent_id: Optional parent ID
            **kwargs: Additional node attributes
            
        Returns:
            The created node
        """
        node = ThoughtNode(
            title=title,
            content=content,
            thought_type=thought_type,
            **kwargs,
        )
        return self.add_node(node, parent_id)
    
    def get_node(self, node_id: str) -> Optional[ThoughtNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_children(self, node_id: str) -> List[ThoughtNode]:
        """Get all children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]
    
    def get_ancestors(self, node_id: str) -> List[ThoughtNode]:
        """Get all ancestors of a node (parent, grandparent, etc.)."""
        ancestors = []
        node = self.nodes.get(node_id)
        while node and node.parent_id:
            parent = self.nodes.get(node.parent_id)
            if parent:
                ancestors.append(parent)
                node = parent
            else:
                break
        return ancestors
    
    def get_path(self, node_id: str) -> List[ThoughtNode]:
        """Get path from root to node."""
        ancestors = self.get_ancestors(node_id)
        ancestors.reverse()
        node = self.nodes.get(node_id)
        if node:
            ancestors.append(node)
        return ancestors
    
    def get_root_nodes(self) -> List[ThoughtNode]:
        """Get all root nodes."""
        return [self.nodes[rid] for rid in self.root_ids if rid in self.nodes]
    
    def get_all_leaves(self) -> List[ThoughtNode]:
        """Get all leaf nodes (no children)."""
        return [
            node for node in self.nodes.values()
            if not node.children_ids
        ]
    
    def get_by_status(self, status: ThoughtStatus) -> List[ThoughtNode]:
        """Get all nodes with a specific status."""
        return [node for node in self.nodes.values() if node.status == status]
    
    def get_in_progress(self) -> List[ThoughtNode]:
        """Get all in-progress nodes."""
        return self.get_by_status(ThoughtStatus.IN_PROGRESS)
    
    def get_pending(self) -> List[ThoughtNode]:
        """Get all pending nodes."""
        return self.get_by_status(ThoughtStatus.PENDING)
    
    def compute_progress(self) -> float:
        """Compute overall tree progress."""
        if not self.nodes:
            return 0.0
        
        total = 0.0
        for node in self.nodes.values():
            if node.status == ThoughtStatus.COMPLETED:
                total += 1.0
            elif node.status == ThoughtStatus.IN_PROGRESS:
                total += node.progress
        
        return total / len(self.nodes)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get tree summary statistics."""
        by_status = {}
        by_type = {}
        
        for node in self.nodes.values():
            status = node.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            thought_type = node.thought_type.value
            by_type[thought_type] = by_type.get(thought_type, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "root_nodes": len(self.root_ids),
            "by_status": by_status,
            "by_type": by_type,
            "progress": self.compute_progress(),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "root_ids": self.root_ids,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "summary": self.get_summary(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThoughtTree":
        """Create from dictionary."""
        tree = cls(
            id=data.get("id", str(uuid.uuid4())),
            investigation_id=data.get("investigation_id", ""),
            root_ids=data.get("root_ids", []),
        )
        
        # Parse nodes
        for nid, node_data in data.get("nodes", {}).items():
            tree.nodes[nid] = ThoughtNode.from_dict(node_data)
        
        # Parse dates
        if data.get("created_at"):
            tree.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            tree.updated_at = datetime.fromisoformat(data["updated_at"])
        
        return tree
    
    def to_stream_format(self) -> List[Dict[str, Any]]:
        """
        Convert to streaming format (flat list with depth info).
        
        Useful for rendering in UI as a flat list with indentation.
        """
        result = []
        
        def traverse(node_id: str, depth: int = 0):
            node = self.nodes.get(node_id)
            if not node:
                return
            
            node_dict = node.to_dict()
            node_dict["depth"] = depth
            result.append(node_dict)
            
            for child_id in node.children_ids:
                traverse(child_id, depth + 1)
        
        for root_id in self.root_ids:
            traverse(root_id)
        
        return result
