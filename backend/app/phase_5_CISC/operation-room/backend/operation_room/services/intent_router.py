import logging
from typing import Dict, Any, Tuple
import re

from operation_room.services.llm_provider import get_llm

logger = logging.getLogger(__name__)

class IntentRouterAgent:
    """
    Analyzes prompts and routes them to specialized agents (e.g., Timeline, Network, Anomaly).
    """

    AVAILABLE_AGENTS = {
        "timeline_agent": "Focuses on temporal sequences, time stomping, sequence of events.",
        "network_agent": "Focuses on IP addresses, ports, data exfiltration, lateral movement.",
        "anomaly_agent": "Focuses on behavioral deviations, statistical outliers, ML scored alerts.",
        "correlation_agent": "Focuses on graph intelligence, entity relationships, blast radius.",
    }

    def __init__(self, llm_provider: str = "ollama"):
        self.llm_provider = llm_provider

    async def route_prompt(self, prompt: str, context: Dict[str, Any] | None = None) -> Tuple[str, str]:
        """
        Takes a raw user prompt, determines the best domain agent to handle it,
        and returns a tuple of (agent_id, reasoning).
        """
        agent_descriptions = "\n".join([f"- {k}: {v}" for k, v in self.AVAILABLE_AGENTS.items()])
        
        system_prompt = f"""You are the NFLIP Intent Router. Your job is to classify an incoming user query into exactly ONE of the available specialized agents based on its domain. 
        
Available Agents:
{agent_descriptions}

Rules:
1. Output MUST be ONLY the agent name followed by a short reason, in this EXACT format: AGENT_ID|REASON
2. If the user asks about timelines or timestamps, choose timeline_agent.
3. If the user asks about exfiltration or IPs, choose network_agent.
4. If the user asks for anomalies, algorithms or outliers, choose anomaly_agent.
5. For everything else (general queries, finding connections), default to correlation_agent.
"""
        
        llm = get_llm(self.llm_provider)
        try:
            response = await llm.generate(prompt, system=system_prompt, max_tokens=100)
            
            # Parse response
            parts = response.split("|", 1)
            if len(parts) == 2 and parts[0].strip() in self.AVAILABLE_AGENTS.keys():
                agent = parts[0].strip()
                reason = parts[1].strip()
                logger.info(f"Routed '{prompt[:30]}...' to {agent}. Reason: {reason}")
                return agent, reason
                
        except Exception as e:
            logger.error(f"Intent routing failed: {str(e)}")
            
        # Fallback keyword matching
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["time", "when", "sequence", "chronological"]):
            return "timeline_agent", "Keyword fallback"
        if any(w in prompt_lower for w in ["ip", "port", "network", "exfiltrate", "byte"]):
            return "network_agent", "Keyword fallback"
        if any(w in prompt_lower for w in ["anomaly", "outlier", "strange", "score", "isolation forest"]):
            return "anomaly_agent", "Keyword fallback"
            
        return "correlation_agent", "Default fallback"

intent_router = IntentRouterAgent()
