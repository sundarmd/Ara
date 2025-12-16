"""
Streaming chat service for SSE-based question answering.

Wraps the Multi-Agent Orchestrator logic and emits events at each processing phase
for real-time frontend display of agent thoughts.
"""
import logging
from typing import AsyncGenerator

from models.schemas import ChatRequest
from services.agent_orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


async def stream_chat_rag(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Streaming chat with multi-agent orchestration.
    Delegates processing to AgentOrchestrator.
    """
    logger.info(f"Processing streaming chat query via Orchestrator")
    
    orchestrator = get_orchestrator()
    async for event_line in orchestrator.process_query(request):
        yield event_line
