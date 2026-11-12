# NFLIP Add-On Features Implementation Plan

## Executive Summary

This plan covers **15 high-impact features** organized into **5 phases** that build progressively on the existing NFLIP architecture. Each phase is independently deployable and adds immediate value.

**Total Estimate:** 8-10 weeks  
**Priority:** Features ordered by impact × ease of integration

---

## Quick Reference: Feature Matrix

| # | Feature | Phase | Days | Impact | Dependencies |
|---|---------|-------|------|--------|--------------|
| 1.1 | MITRE ATT&CK Mapper | 1 | 3 | 🔴 High | - |
| 1.2 | Threat Intel Enrichment | 1 | 3 | 🔴 High | - |
| 1.3 | IOC Extractor | 1 | 2 | 🟡 Medium | - |
| 2.1 | Natural Language Query | 2 | 4 | 🔴 High | - |
| 2.2 | Auto Report Narrator | 2 | 3 | 🟡 Medium | - |
| 3.1 | Interactive Graph Explorer | 3 | 4 | 🔴 High | - |
| 3.2 | Geo-IP Map | 3 | 2 | 🟡 Medium | 1.2 |
| 3.3 | Heatmap Calendar | 3 | 1 | 🟢 Low | - |
| 4.1 | SIEM Connector | 4 | 5 | 🔴 High | - |
| 4.2 | Ticketing Integration | 4 | 3 | 🟡 Medium | - |
| 4.3 | Webhook Notifications | 4 | 1 | 🟢 Low | - |
| 5.1 | RBAC Permissions | 5 | 4 | 🔴 High | - |
| 5.2 | Evidence Redaction | 5 | 2 | 🟡 Medium | - |
| 5.3 | Digital Signatures | 5 | 2 | 🟡 Medium | - |

---

## Phase 1: Intelligence Enrichment (Week 1-2)
*Foundation for evidence-aware AI features*

### 1.1 MITRE ATT&CK Mapper Tool

**Purpose:** Auto-map every finding to MITRE tactics/techniques with TTP cards

**Files to Create:**
```
backend/app/tools/mitre_tool.py           # New Universal Tool
backend/app/services/mitre_service.py     # MITRE data + mapping logic
backend/app/data/mitre_attack.json        # ATT&CK framework cache (15MB)
frontend/src/components/studio-v4/panels/MITREPanel.tsx
frontend/src/components/studio-v4/charts/AttackChainChart.tsx
```

**MitreService Implementation:**
```python
class MitreService:
    def __init__(self):
        self.tactics = load_tactics()      # 14 tactics
        self.techniques = load_techniques() # 200+ techniques
        self.technique_index = build_search_index()
    
    def map_event_to_technique(self, event: Dict) -> List[MitreMatch]:
        """
        Use LLM + keyword matching to find best technique.
        
        Example:
        Input: {"action": "login", "status": "failed", "count": 50}
        Output: [MitreMatch(tactic="Credential Access", 
                           technique="T1110", 
                           name="Brute Force",
                           confidence=0.92)]
        """
        # 1. Extract action keywords from event
        keywords = self._extract_keywords(event)
        
        # 2. Search technique descriptions (fuzzy match)
        candidates = self.technique_index.search(keywords, limit=5)
        
        # 3. LLM confirmation for ambiguous matches
        if len(candidates) > 1:
            best = await self.llm.select_best_technique(event, candidates)
            return [best]
        
        return candidates
    
    def build_attack_chain(self, findings: List) -> AttackChain:
        """Order findings by kill-chain phase (Recon → Impact)"""
        mapped = [self.map_event_to_technique(f) for f in findings]
        return AttackChain(
            phases=self._group_by_tactic(mapped),
            timeline=self._build_timeline(mapped)
        )
    
    def export_navigator_json(self, chain: AttackChain) -> str:
        """Export to MITRE ATT&CK Navigator format"""
        return json.dumps({
            "name": "Investigation Attack Chain",
            "versions": {"attack": "14", "navigator": "4.9"},
            "techniques": [
                {"techniqueID": t.id, "score": t.confidence * 100}
                for t in chain.all_techniques
            ]
        })
```

**MITRETool (Universal Tool Interface):**
```python
class MITRETool(ModuleTool):
    tool_id = "mitre_mapping"
    tool_name = "MITRE ATT&CK Mapper"
    tool_category = ToolCategory.ANALYSIS
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="map_events",
                description="Map events to MITRE ATT&CK techniques",
                input_schema={
                    "events": "List of events to map",
                    "min_confidence": "Minimum confidence threshold (0-1)"
                },
                output_schema={
                    "mappings": "List of event-to-technique mappings",
                    "attack_chain": "Ordered kill-chain"
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH],
                supports_streaming=True
            ),
            ToolCapability(
                name="build_chain",
                description="Build kill-chain visualization",
                visualization_types=[VisualizationType.SANKEY]
            ),
            ToolCapability(
                name="get_mitigations",
                description="Get recommended mitigations for techniques"
            ),
            ToolCapability(
                name="export_navigator",
                description="Export to MITRE Navigator JSON"
            )
        ]
```

**Frontend MITREPanel:**
```typescript
const MITREPanel = ({ caseId }) => {
  const { data: attackChain } = useAttackChain(caseId);
  
  return (
    <div className="mitre-panel">
      {/* Kill-chain matrix heatmap */}
      <KillChainMatrix 
        tactics={attackChain?.phases}
        onTacticClick={(tactic) => setSelectedTactic(tactic)}
      />
      
      {/* Technique cards with evidence links */}
      <TechniqueCardList
        techniques={selectedTacticTechniques}
        onTechniqueClick={(tech) => scrollToEvidence(tech.evidenceRef)}
      />
      
      {/* Export button */}
      <Button onClick={() => exportToNavigator(attackChain)}>
        Export to ATT&CK Navigator
      </Button>
    </div>
  );
};
```

**Integration Points:**
- Hook into `correlation_agent.py` during synthesis phase
- Add to investigation SSE stream: `event_type: "mitre_mapping"`
- Auto-populate canvas with MITRE section after investigation

---

### 1.2 Threat Intelligence Enrichment

**Purpose:** One-click lookup for IPs, domains, hashes against external threat feeds

**Files to Create:**
```
backend/app/services/threat_intel_service.py
backend/app/routes/threat_intel.py
frontend/src/components/studio-v4/panels/ThreatIntelPanel.tsx
frontend/src/components/common/EntityEnrichmentPopover.tsx
```

**ThreatIntelService:**
```python
class ThreatIntelService:
    def __init__(self):
        self.providers = {
            "virustotal": VirusTotalClient(api_key=settings.VT_API_KEY),
            "abuseipdb": AbuseIPDBClient(api_key=settings.ABUSEIPDB_KEY),
            "shodan": ShodanClient(api_key=settings.SHODAN_KEY),
            "otx": OTXClient(api_key=settings.OTX_KEY),
        }
        self.cache = TTLCache(maxsize=10000, ttl=3600)  # 1hr cache
    
    async def enrich_entity(
        self, 
        value: str, 
        entity_type: str
    ) -> EnrichmentResult:
        """
        Query all relevant providers for entity.
        
        Returns aggregated reputation score and details.
        """
        cache_key = f"{entity_type}:{value}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        results = {}
        
        if entity_type == "ip":
            results["virustotal"] = await self.providers["virustotal"].check_ip(value)
            results["abuseipdb"] = await self.providers["abuseipdb"].check(value)
            results["shodan"] = await self.providers["shodan"].host(value)
        
        elif entity_type == "domain":
            results["virustotal"] = await self.providers["virustotal"].check_domain(value)
            results["otx"] = await self.providers["otx"].get_indicators(value)
        
        elif entity_type == "hash":
            results["virustotal"] = await self.providers["virustotal"].check_hash(value)
        
        enrichment = EnrichmentResult(
            entity=value,
            entity_type=entity_type,
            reputation_score=self._calculate_score(results),
            is_malicious=self._is_malicious(results),
            risk_level=self._calculate_risk(results),  # LOW/MEDIUM/HIGH/CRITICAL
            details=results,
            last_checked=datetime.utcnow()
        )
        
        self.cache[cache_key] = enrichment
        return enrichment
    
    async def bulk_enrich(
        self, 
        entities: List[Tuple[str, str]]  # (value, type)
    ) -> Dict[str, EnrichmentResult]:
        """Batch enrichment with rate limiting"""
        results = {}
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def enrich_one(value, etype):
            async with semaphore:
                results[value] = await self.enrich_entity(value, etype)
        
        await asyncio.gather(*[
            enrich_one(v, t) for v, t in entities
        ])
        
        return results
    
    def _calculate_score(self, results: Dict) -> float:
        """Calculate weighted reputation score 0-100"""
        weights = {"virustotal": 0.4, "abuseipdb": 0.3, "shodan": 0.2, "otx": 0.1}
        score = 0
        for provider, weight in weights.items():
            if provider in results:
                score += results[provider].get("score", 50) * weight
        return score
```

**API Routes:**
```python
@router.post("/api/threat-intel/enrich")
async def enrich_entity(request: EnrichRequest) -> EnrichmentResult:
    return await threat_intel_service.enrich_entity(
        request.value, 
        request.entity_type
    )

@router.post("/api/threat-intel/bulk")
async def bulk_enrich(request: BulkEnrichRequest) -> Dict[str, EnrichmentResult]:
    return await threat_intel_service.bulk_enrich(request.entities)

@router.get("/api/threat-intel/providers")
async def list_providers():
    return {
        "providers": [
            {"name": "VirusTotal", "types": ["ip", "domain", "hash"], "enabled": bool(settings.VT_API_KEY)},
            {"name": "AbuseIPDB", "types": ["ip"], "enabled": bool(settings.ABUSEIPDB_KEY)},
            {"name": "Shodan", "types": ["ip"], "enabled": bool(settings.SHODAN_KEY)},
        ]
    }
```

**Frontend EntityEnrichmentPopover:**
```typescript
const EntityEnrichmentPopover = ({ entity, entityType, children }) => {
  const { data, isLoading } = useEnrichment(entity, entityType);
  
  return (
    <Popover>
      <PopoverTrigger asChild>
        {children}
      </PopoverTrigger>
      <PopoverContent className="w-80">
        {isLoading ? (
          <Skeleton className="h-24" />
        ) : (
          <div className="enrichment-card">
            {/* Risk badge */}
            <Badge variant={getRiskVariant(data.risk_level)}>
              {data.risk_level}
            </Badge>
            
            {/* Reputation score */}
            <div className="score">
              <span className="text-2xl font-bold">{data.reputation_score}</span>
              <span className="text-muted">/100</span>
            </div>
            
            {/* Provider details */}
            <Accordion type="single" collapsible>
              {Object.entries(data.details).map(([provider, info]) => (
                <AccordionItem key={provider} value={provider}>
                  <AccordionTrigger>{provider}</AccordionTrigger>
                  <AccordionContent>
                    <ProviderDetails data={info} />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
            
            {/* Actions */}
            <div className="flex gap-2 mt-4">
              <Button size="sm" onClick={() => addToIOCList(entity)}>
                Add to IOC List
              </Button>
              <Button size="sm" variant="outline" onClick={() => viewFullReport(entity)}>
                Full Report
              </Button>
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};
```

---

### 1.3 IOC Extractor & Exporter

**Purpose:** Extract all IOCs from investigation, export to STIX/OpenIOC/CSV

**Files to Create:**
```
backend/app/services/ioc_service.py
backend/app/routes/ioc.py
frontend/src/components/studio-v4/dialogs/IOCExportDialog.tsx
```

**IOCService:**
```python
class IOCService:
    ioc_patterns = {
        "ipv4": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
        "ipv6": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),
        "domain": re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b"),
        "md5": re.compile(r"\b[a-fA-F0-9]{32}\b"),
        "sha1": re.compile(r"\b[a-fA-F0-9]{40}\b"),
        "sha256": re.compile(r"\b[a-fA-F0-9]{64}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "url": re.compile(r"https?://[^\s<>\"']+"),
        "cve": re.compile(r"CVE-\d{4}-\d{4,}"),
    }
    
    async def extract_from_case(self, case_id: str) -> List[IOC]:
        """Extract all IOCs from case evidence and findings"""
        iocs = []
        
        # Get all text content from case
        evidence = await vault.get_all_evidence(case_id)
        findings = await self._get_findings_text(case_id)
        
        all_text = "\n".join([e.content for e in evidence] + findings)
        
        # Extract IOCs
        for ioc_type, pattern in self.ioc_patterns.items():
            for match in pattern.finditer(all_text):
                value = match.group()
                
                # Skip internal IPs
                if ioc_type in ["ipv4", "ipv6"] and self._is_internal(value):
                    continue
                
                iocs.append(IOC(
                    type=ioc_type,
                    value=value,
                    context=self._get_context(all_text, match.start()),
                    first_seen=datetime.utcnow(),
                    confidence=0.8 if self._validate_ioc(value, ioc_type) else 0.5
                ))
        
        # Deduplicate
        return list({(ioc.type, ioc.value): ioc for ioc in iocs}.values())
    
    def export_stix(self, iocs: List[IOC], case_info: Dict) -> str:
        """Export to STIX 2.1 bundle"""
        stix_objects = [
            stix2.Indicator(
                name=f"{ioc.type}: {ioc.value}",
                pattern=self._to_stix_pattern(ioc),
                pattern_type="stix",
                valid_from=ioc.first_seen,
                confidence=int(ioc.confidence * 100),
                labels=[ioc.type]
            )
            for ioc in iocs
        ]
        
        bundle = stix2.Bundle(objects=stix_objects)
        return bundle.serialize(pretty=True)
    
    def export_openioc(self, iocs: List[IOC]) -> str:
        """Export to OpenIOC XML format"""
        # Implementation using lxml
        pass
    
    def export_csv(self, iocs: List[IOC]) -> str:
        """Export to CSV"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["type", "value", "confidence", "context"])
        writer.writeheader()
        for ioc in iocs:
            writer.writerow(ioc.to_dict())
        return output.getvalue()
```

---

## Phase 2: Natural Language Interface (Week 3-4)
*AI-powered query and interaction*

### 2.1 Natural Language Evidence Query

**Purpose:** Ask questions like "Show all failed logins after midnight from external IPs"

**Files to Create:**
```
backend/app/services/nlp_query_service.py
backend/app/routes/nlp_query.py
frontend/src/components/studio-v4/NLPSearchBar.tsx
frontend/src/hooks/useNLPQuery.ts
```

**NLPQueryService:**
```python
class NLPQueryService:
    def __init__(self, llm_service: LLMService, vault: VaultService):
        self.llm = llm_service
        self.vault = vault
        self.schema_prompt = self._build_schema_prompt()
    
    async def parse_query(
        self, 
        natural_query: str, 
        case_id: str
    ) -> StructuredQuery:
        """
        Convert natural language to structured query.
        
        Example:
        Input: "Show failed logins from 192.168.1.* after 2 PM"
        Output: {
            "action": "search",
            "entity_type": "login_event",
            "filters": {
                "status": "failed",
                "source_ip": {"pattern": "192.168.1.*"},
                "timestamp": {"gte": "14:00:00"}
            },
            "sort": {"field": "timestamp", "order": "desc"},
            "limit": 100
        }
        """
        # Get available fields from case schema
        schema = await self.vault.get_case_schema(case_id)
        
        prompt = f"""
        Convert this natural language query to a structured search query.
        
        Question: {natural_query}
        
        Available fields:
        {json.dumps(schema, indent=2)}
        
        Return a JSON object with:
        - action: "search" | "count" | "aggregate"
        - entity_type: type of data to query
        - filters: dictionary of field -> condition
        - sort: optional sorting
        - limit: max results (default 100)
        
        For conditions, use:
        - Direct value for equality
        - {{"pattern": "..."}} for wildcards
        - {{"gte": ..., "lte": ...}} for ranges
        - {{"in": [...]}} for multiple values
        """
        
        response = await self.llm.generate(prompt, temperature=0.1)
        return StructuredQuery.model_validate_json(response)
    
    async def execute_and_explain(
        self, 
        query: StructuredQuery, 
        case_id: str,
        original_question: str
    ) -> QueryResult:
        """Execute query and generate explanation"""
        # Execute
        results = await self.vault.execute_query(case_id, query)
        
        # Generate explanation
        explanation = await self.llm.generate(f"""
        The user asked: "{original_question}"
        
        I found {len(results)} results. Here's a summary:
        {json.dumps(results[:5], indent=2)}
        
        Provide a 1-2 sentence explanation of what was found.
        """)
        
        return QueryResult(
            query=query,
            results=results,
            explanation=explanation,
            result_count=len(results)
        )
```

**NLPSearchBar Component:**
```typescript
const NLPSearchBar = ({ caseId }) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const { execute, results, isLoading, explanation } = useNLPQuery(caseId);
  
  // Example queries based on case type
  const exampleQueries = [
    "Show all login failures in the last 24 hours",
    "Find connections to external IPs",
    "What files were accessed by admin users?",
    "Count events by user",
  ];
  
  return (
    <div className="nlp-search">
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-10"
          placeholder="Ask a question about the evidence..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            updateSuggestions(e.target.value);
          }}
          onKeyDown={(e) => e.key === 'Enter' && execute(query)}
        />
      </div>
      
      {/* Suggestions dropdown */}
      {suggestions.length > 0 && (
        <div className="suggestions-dropdown">
          {suggestions.map(s => (
            <div key={s} onClick={() => { setQuery(s); execute(s); }}>
              {s}
            </div>
          ))}
        </div>
      )}
      
      {/* Results */}
      {isLoading && <Skeleton className="h-48" />}
      
      {results && (
        <div className="results">
          <p className="explanation">{explanation}</p>
          <DataTable data={results} />
        </div>
      )}
    </div>
  );
};
```

---

### 2.2 Auto Report Narrator

**Purpose:** Generate executive summary and narrative sections automatically

**Files to Create:**
```
backend/app/services/narrator_service.py
backend/app/routes/narrator.py
frontend/src/components/studio-v4/dialogs/NarratorDialog.tsx
```

**NarratorService:**
```python
class NarratorService:
    section_templates = {
        "executive_summary": """
            Write a 2-paragraph executive summary of this forensic investigation.
            
            Key findings: {findings}
            Timeline: {timeline}
            Impact assessment: {impact}
            
            Requirements:
            - First paragraph: What happened and how serious it is
            - Second paragraph: Key recommendations
            - Use formal business language
            - Avoid technical jargon
            - Be specific about dates, systems, and impact
        """,
        
        "technical_analysis": """
            Write a detailed technical analysis section covering:
            
            Attack Vector: {attack_vector}
            Affected Systems: {systems}
            Evidence Timeline: {timeline}
            IOCs Discovered: {iocs}
            
            Include:
            - Specific technical details with evidence references
            - Clear cause-and-effect analysis
            - MITRE ATT&CK technique references where applicable
        """,
        
        "recommendations": """
            Based on these investigation findings, generate actionable recommendations:
            
            Findings: {findings}
            Affected Systems: {systems}
            
            Structure as:
            1. Immediate Actions (next 24-48 hours)
            2. Short-term Improvements (next 30 days)
            3. Long-term Strategic Changes (next quarter)
            
            Be specific and actionable.
        """
    }
    
    async def generate_section(
        self,
        section_type: str,
        context: Dict,
        style: str = "formal"
    ) -> AsyncGenerator[str, None]:
        """Generate narrative section with streaming"""
        template = self.section_templates[section_type]
        prompt = template.format(**context)
        
        async for chunk in self.llm.stream(prompt):
            yield chunk
    
    async def generate_full_report(
        self,
        case_id: str,
        sections: List[str] = None
    ) -> AsyncGenerator[ReportChunk, None]:
        """Stream complete report narrative"""
        if sections is None:
            sections = ["executive_summary", "technical_analysis", "recommendations"]
        
        context = await self._build_context(case_id)
        
        for section in sections:
            yield ReportChunk(
                type="section_start",
                section=section,
                title=self._get_section_title(section)
            )
            
            async for text in self.generate_section(section, context):
                yield ReportChunk(
                    type="text",
                    section=section,
                    content=text
                )
            
            yield ReportChunk(type="section_end", section=section)
```

---

## Phase 3: Interactive Visualization (Week 5-6)
*Advanced visual exploration tools*

### 3.1 Interactive Graph Explorer

**Purpose:** D3.js/React-Flow network graph with drill-down capability

**Files to Create:**
```
frontend/src/components/studio-v4/panels/GraphExplorerPanel.tsx
frontend/src/components/studio-v4/graph/InteractiveGraph.tsx
frontend/src/components/studio-v4/graph/NodeInspector.tsx
frontend/src/components/studio-v4/graph/GraphControls.tsx
backend/app/routes/graph.py
```

**Backend Graph API:**
```python
@router.get("/api/graph/{case_id}/neighborhood")
async def get_neighborhood(
    case_id: str, 
    node_id: str, 
    depth: int = 2,
    max_nodes: int = 50
):
    """Get subgraph around a node"""
    graph = await correlation_service.get_graph(case_id)
    subgraph = graph.neighborhood(node_id, depth=depth)
    
    # Limit size for performance
    if len(subgraph.nodes) > max_nodes:
        subgraph = subgraph.most_connected(max_nodes)
    
    return {
        "nodes": [node_to_dict(n) for n in subgraph.nodes],
        "edges": [edge_to_dict(e) for e in subgraph.edges],
        "center_node": node_id,
        "total_nodes": len(graph.nodes)
    }

@router.get("/api/graph/{case_id}/paths")
async def find_paths(
    case_id: str, 
    source: str, 
    target: str, 
    max_length: int = 5
):
    """Find paths between two nodes"""
    graph = await correlation_service.get_graph(case_id)
    paths = graph.find_all_paths(source, target, max_length=max_length)
    
    return {
        "paths": [
            {"nodes": path, "length": len(path) - 1}
            for path in paths[:10]  # Limit to top 10
        ],
        "shortest_length": len(paths[0]) - 1 if paths else None
    }

@router.get("/api/graph/{case_id}/metrics")
async def get_node_metrics(case_id: str, node_id: str):
    """Get centrality and other metrics for a node"""
    graph = await correlation_service.get_graph(case_id)
    
    return {
        "node_id": node_id,
        "degree": graph.degree(node_id),
        "betweenness": graph.betweenness_centrality(node_id),
        "pagerank": graph.pagerank(node_id),
        "connected_components": graph.num_connected_components(),
        "is_bridge": graph.is_bridge_node(node_id)
    }
```

**InteractiveGraph Component:**
```typescript
import ReactFlow, {
  Node,
  Edge,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
} from 'reactflow';

const InteractiveGraph = ({ caseId, initialNodeId }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(false);
  const reactFlowInstance = useRef(null);
  
  // Load initial neighborhood
  useEffect(() => {
    if (initialNodeId) {
      loadNeighborhood(initialNodeId);
    }
  }, [initialNodeId]);
  
  const loadNeighborhood = async (nodeId: string) => {
    setLoading(true);
    const data = await fetchNeighborhood(caseId, nodeId);
    
    // Convert to ReactFlow format
    const rfNodes = data.nodes.map(n => ({
      id: n.id,
      data: { label: n.label, ...n.properties },
      position: calculatePosition(n, data.nodes.length),
      type: getNodeType(n.entity_type),
      style: getNodeStyle(n)
    }));
    
    const rfEdges = data.edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: e.is_suspicious
    }));
    
    setNodes(rfNodes);
    setEdges(rfEdges);
    setLoading(false);
  };
  
  const onNodeClick = async (event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  };
  
  const onNodeDoubleClick = async (event: React.MouseEvent, node: Node) => {
    // Expand this node's neighborhood
    await loadNeighborhood(node.id);
  };
  
  const findPath = async (targetId: string) => {
    if (!selectedNode) return;
    
    const paths = await fetchPaths(caseId, selectedNode.id, targetId);
    highlightPaths(paths);
  };
  
  return (
    <div className="graph-explorer h-full">
      {loading && <LoadingOverlay />}
      
      <GraphControls
        onZoomIn={() => reactFlowInstance.current?.zoomIn()}
        onZoomOut={() => reactFlowInstance.current?.zoomOut()}
        onFitView={() => reactFlowInstance.current?.fitView()}
        onExport={() => exportGraphAsPNG()}
        onFindPath={() => setPathFindingMode(true)}
      />
      
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        nodeTypes={customNodeTypes}
        fitView
      >
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>
      
      {/* Node inspector sidebar */}
      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          caseId={caseId}
          onClose={() => setSelectedNode(null)}
          onFindPath={findPath}
        />
      )}
    </div>
  );
};
```

---

### 3.2 Geo-IP Map Visualization

**Purpose:** World map showing connection origins/destinations

**Files to Create:**
```
backend/app/services/geoip_service.py
frontend/src/components/studio-v4/charts/GeoIPMap.tsx
frontend/src/components/studio-v4/panels/GeoPanel.tsx
```

**Implementation:** Uses MaxMind GeoLite2 database + react-simple-maps

---

### 3.3 Heatmap Calendar

**Purpose:** Activity density heatmap showing patterns over time

**Quick Win - 1 day implementation**

```typescript
const HeatmapCalendar = ({ data, onCellClick }) => {
  // data: { date: string, hour: number, value: number }[]
  
  const maxValue = Math.max(...data.map(d => d.value));
  
  return (
    <div className="heatmap-calendar">
      <div className="hour-labels">
        {Array.from({ length: 24 }, (_, i) => (
          <span key={i}>{i}:00</span>
        ))}
      </div>
      
      <div className="calendar-grid">
        {data.map(cell => (
          <div
            key={`${cell.date}-${cell.hour}`}
            className="heatmap-cell"
            style={{
              backgroundColor: `rgba(59, 130, 246, ${cell.value / maxValue})`
            }}
            title={`${cell.date} ${cell.hour}:00 - ${cell.value} events`}
            onClick={() => onCellClick(cell)}
          />
        ))}
      </div>
    </div>
  );
};
```

---

## Phase 4: Integration & Workflow (Week 7-8)

### 4.1 SIEM Connector (Splunk/Elastic)
### 4.2 Ticketing Integration (Jira/ServiceNow)  
### 4.3 Webhook Notifications

*(Detailed implementations similar to above)*

---

## Phase 5: Security & Compliance (Week 9-10)

### 5.1 RBAC Permissions
### 5.2 Evidence Redaction
### 5.3 Digital Signatures

*(Detailed implementations similar to above)*

---

## Dependencies to Add

**Backend (requirements.txt):**
```txt
mitreattack-python>=3.0.0    # MITRE ATT&CK framework
geoip2>=4.8.0                # MaxMind GeoIP
vt-py>=0.18.0                # VirusTotal API
stix2>=3.0.1                 # STIX 2.1 export
aiohttp>=3.9.0               # Async HTTP
cryptography>=42.0.0         # Digital signatures
python-jose>=3.3.0           # JWT for auth
```

**Frontend (package.json):**
```json
{
  "reactflow": "^11.10.0",
  "react-simple-maps": "^3.0.0",
  "d3-scale-chromatic": "^3.0.0"
}
```

---

## Quick Start: First Feature to Implement

**Recommended:** Start with **IOC Extractor (1.3)** - it's:
- Standalone (no external dependencies)
- 2 days to implement
- Immediately useful
- Good foundation for Threat Intel integration

```bash
# Create the files
touch backend/app/services/ioc_service.py
touch backend/app/routes/ioc.py
touch frontend/src/components/studio-v4/dialogs/IOCExportDialog.tsx
```

---

*Plan Version: 1.0*
*Created: April 2026*
*For: NFLIP Operation Room v0.2.0*
