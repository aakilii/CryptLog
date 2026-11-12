"""
WebSocket Support for Deep Research.

Provides real-time bidirectional communication for:
- Progress updates
- Human-in-loop questions
- Thought streaming
- Plan updates
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
import logging


logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """A connected WebSocket client."""
    websocket: WebSocket
    investigation_id: str
    client_id: str
    connected_at: datetime = field(default_factory=datetime.now)
    subscriptions: Set[str] = field(default_factory=set)
    
    async def send(self, data: Dict[str, Any]) -> bool:
        """Send data to client."""
        try:
            await self.websocket.send_json(data)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {self.client_id}: {e}")
            return False


class WebSocketManager:
    """
    Manages WebSocket connections for deep research.
    
    Features:
    - Connection management
    - Topic subscriptions
    - Broadcast to investigation
    - Message handling
    """
    
    def __init__(self):
        """Initialize manager."""
        self._clients: Dict[str, WebSocketClient] = {}
        self._investigations: Dict[str, Set[str]] = {}  # inv_id -> client_ids
        self._handlers: Dict[str, Callable] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        investigation_id: str,
        client_id: str,
    ) -> WebSocketClient:
        """Accept a new connection."""
        await websocket.accept()
        
        client = WebSocketClient(
            websocket=websocket,
            investigation_id=investigation_id,
            client_id=client_id,
        )
        
        self._clients[client_id] = client
        
        # Add to investigation
        if investigation_id not in self._investigations:
            self._investigations[investigation_id] = set()
        self._investigations[investigation_id].add(client_id)
        
        logger.info(f"WebSocket connected: {client_id} -> {investigation_id}")
        
        # Send welcome
        await client.send({
            "type": "connected",
            "client_id": client_id,
            "investigation_id": investigation_id,
            "timestamp": datetime.now().isoformat(),
        })
        
        return client
    
    def disconnect(self, client_id: str) -> None:
        """Handle disconnection."""
        if client_id not in self._clients:
            return
        
        client = self._clients.pop(client_id)
        
        # Remove from investigation
        if client.investigation_id in self._investigations:
            self._investigations[client.investigation_id].discard(client_id)
            if not self._investigations[client.investigation_id]:
                del self._investigations[client.investigation_id]
        
        logger.info(f"WebSocket disconnected: {client_id}")
    
    async def broadcast_to_investigation(
        self,
        investigation_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Broadcast message to all clients on an investigation."""
        if investigation_id not in self._investigations:
            return 0
        
        client_ids = list(self._investigations[investigation_id])
        sent = 0
        
        for client_id in client_ids:
            if client_id in self._clients:
                if await self._clients[client_id].send(data):
                    sent += 1
        
        return sent
    
    async def send_to_client(
        self,
        client_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Send message to a specific client."""
        if client_id not in self._clients:
            return False
        return await self._clients[client_id].send(data)
    
    def register_handler(
        self,
        message_type: str,
        handler: Callable[[str, Dict[str, Any]], Any],
    ) -> None:
        """Register a message handler."""
        self._handlers[message_type] = handler
    
    async def handle_message(
        self,
        client_id: str,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle incoming message."""
        message_type = message.get("type")
        
        if message_type in self._handlers:
            try:
                result = await self._handlers[message_type](client_id, message)
                return result
            except Exception as e:
                logger.error(f"Handler error for {message_type}: {e}")
                return {"type": "error", "message": str(e)}
        
        return None
    
    async def listen(self, client: WebSocketClient) -> None:
        """Listen for messages from a client."""
        try:
            while True:
                data = await client.websocket.receive_json()
                response = await self.handle_message(client.client_id, data)
                
                if response:
                    await client.send(response)
                    
        except WebSocketDisconnect:
            self.disconnect(client.client_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.disconnect(client.client_id)
    
    # Convenience methods for common events
    
    async def send_thought_update(
        self,
        investigation_id: str,
        thought_id: str,
        content: str,
        status: str = "in_progress",
    ) -> None:
        """Send thought update."""
        await self.broadcast_to_investigation(investigation_id, {
            "type": "thought_update",
            "thought_id": thought_id,
            "content": content,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def send_question(
        self,
        investigation_id: str,
        question_id: str,
        question: str,
        options: Optional[List[str]] = None,
        priority: str = "medium",
    ) -> None:
        """Send human-in-loop question."""
        await self.broadcast_to_investigation(investigation_id, {
            "type": "question",
            "question_id": question_id,
            "question": question,
            "options": options,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def send_progress_update(
        self,
        investigation_id: str,
        phase: str,
        step: Optional[str] = None,
        progress: float = 0.0,
    ) -> None:
        """Send progress update."""
        await self.broadcast_to_investigation(investigation_id, {
            "type": "progress_update",
            "phase": phase,
            "step": step,
            "current_task": step,
            "progress": progress,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def send_plan_update(
        self,
        investigation_id: str,
        plan_id: str,
        change_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Send plan update."""
        await self.broadcast_to_investigation(investigation_id, {
            "type": "plan_update",
            "plan_id": plan_id,
            "change_type": change_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_client_count(self, investigation_id: Optional[str] = None) -> int:
        """Get number of connected clients."""
        if investigation_id:
            return len(self._investigations.get(investigation_id, set()))
        return len(self._clients)
    
    def get_investigations_with_clients(self) -> List[str]:
        """Get list of investigations with connected clients."""
        return list(self._investigations.keys())

    # ═══════════════════════════════════════════════════════════════
    # Redis Pub/Sub Subscriber (Celery Worker → WebSocket Relay)
    # ═══════════════════════════════════════════════════════════════

    _redis_tasks: Dict[str, asyncio.Task] = {}

    def start_redis_subscriber(self, investigation_id: str) -> None:
        """
        Start a background task that subscribes to the Redis Pub/Sub
        channel for a specific investigation and relays messages to
        all connected WebSocket clients.
        
        Called automatically when a Celery job is dispatched.
        """
        if investigation_id in self._redis_tasks:
            task = self._redis_tasks[investigation_id]
            if not task.done():
                return

        self._redis_tasks[investigation_id] = asyncio.create_task(
            self._redis_subscribe_loop(investigation_id)
        )
        logger.info(f"[WS] Started Redis subscriber for {investigation_id}")

    async def _redis_subscribe_loop(self, investigation_id: str) -> None:
        """Subscribe to Redis channel and relay events to WebSocket clients."""
        try:
            import redis.asyncio as aioredis
            import os

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = aioredis.from_url(redis_url)
            pubsub = r.pubsub()
            channel = f"nflip:report:{investigation_id}"

            await pubsub.subscribe(channel)
            logger.info(f"[WS] Subscribed to Redis channel: {channel}")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                event_type = data.get("event_type", "")

                # Relay to all connected WebSocket clients
                await self.broadcast_to_investigation(investigation_id, {
                    "type": "celery_event",
                    "event_type": event_type,
                    "data": data.get("data", {}),
                    "progress": data.get("progress", 0),
                    "timestamp": data.get("timestamp", datetime.now().isoformat()),
                })

                # Stop subscriber on terminal events
                if event_type in ("job_completed", "job_failed"):
                    logger.info(f"[WS] Redis subscriber ending for {investigation_id}: {event_type}")
                    break

            await pubsub.unsubscribe(channel)
            await r.aclose()

        except ImportError:
            logger.debug("[WS] redis.asyncio not available — Redis subscriber disabled")
        except asyncio.CancelledError:
            logger.info(f"[WS] Redis subscriber cancelled for {investigation_id}")
        except Exception as e:
            logger.warning(f"[WS] Redis subscriber error for {investigation_id}: {e}")
        finally:
            self._redis_tasks.pop(investigation_id, None)

    def stop_redis_subscriber(self, investigation_id: str) -> None:
        """Stop the Redis subscriber for an investigation."""
        task = self._redis_tasks.pop(investigation_id, None)
        if task and not task.done():
            task.cancel()


# Global manager
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager

