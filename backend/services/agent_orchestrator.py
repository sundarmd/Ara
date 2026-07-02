"""
Agent orchestrator using LangChain and Mistral.

This module handles:
- Tool-calling workflow for query interpretation
- Tool selection and execution (RAG, SQL, Web) using LangChain
- Response generation with streaming thoughts
"""
import logging
import json
import re
from typing import Optional, List, Dict, Any, AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import Tool

from config.settings import settings
from services.tools import AVAILABLE_TOOLS, reset_search_filter_scope, set_search_filter_scope
from models.schemas import ChatRequest, StreamEventType

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Tool-calling orchestrator using LangChain + Mistral (via OpenAI Adapter) for planning and execution.
    """
    
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.endpoint = settings.MISTRAL_CHAT_ENDPOINT
        self.model_name = settings.MISTRAL_CHAT_MODEL
        
        # Initialize LangChain OpenAI Adapter pointing to Mistral
        # Mistral API is OpenAI compatible
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.mistral.ai/v1",
            model=self.model_name,
            temperature=0,
            stop=[
                "\nSources:", 
                "\nReferences:", 
                "\n**Sources", 
                "\n**References", 
                "\n# Sources", 
                "\n# References"
            ]
        )
        
        # Bind tools to the model
        self.llm_with_tools = self.llm.bind_tools(AVAILABLE_TOOLS)
        
        # Map tool names to functions for execution
        self.tool_map = {t.name: t for t in AVAILABLE_TOOLS}
    
    async def process_query(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Process a user query using LangChain's AgentExecutor.
        Yields SSE events: thought, token, complete, error.
        """
        # 1. PLAN: Analyze query
        # 1. PLAN: Analyze query
        # Initial thought removed per user request for cleaner UI

        search_filter_token = None
        
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate
            from services.prompt_loader import load_prompt
            
            # Load system prompt from markdown file
            system_prompt = load_prompt("agent_system")
            
            # Define prompt with explicit thought requirement
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # Create Agent
            agent = create_tool_calling_agent(self.llm, AVAILABLE_TOOLS, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=AVAILABLE_TOOLS, verbose=True)
            
            # Friendly tool names
            TOOL_NAMES = {
                "query_recommendations": "Internal Investment Database",
                "search_knowledge_base": "Research Report Knowledge Base",
                "web_search": "Live Web Search"
            }

            # Execute with streaming
            # Hack: We need a simpler history management for now
            history = []
            for m in request.messages[:-1]: # All except last
                if m.role == "user":
                    history.append(("human", m.content))
                elif m.role == "assistant":
                    history.append(("ai", m.content))

            input_text = request.messages[-1].content
            
            # Streaming state
            buffer = ""
            in_thought_block = False
            collected_sources = []
            search_filter_token = set_search_filter_scope(
                bank=request.bank,
                asset_class=request.asset_class,
            )
            
            async for event in agent_executor.astream_events(
                {"input": input_text, "chat_history": history},
                version="v1"
            ):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    # ... (Existing stream logic) ...
                    chunk = event["data"]["chunk"]
                    content = chunk.content
                    
                    # Fix for "can only concatenate str (not "list") to str"
                    if isinstance(content, list):
                        # If content is a list (e.g. multimodal or complex blocks), join it
                        # Filter out non-string elements if necessary, but usually it's text chunks
                        content = "".join([str(c) for c in content if c])
                        
                    if content:
                        buffer += content
                        # LOGIC: Check for transitions
                        while True:
                            if not in_thought_block:
                                # Look for open tag (case-insensitive)
                                match = re.search(r'<thought>', buffer, re.IGNORECASE)
                                if match:
                                    start_idx = match.start()
                                    in_thought_block = True
                                    # Update buffer to start AFTER the tag
                                    buffer = buffer[match.end():]
                                    continue
                                
                                # Leakage Guard
                                # If buffer ends with partial tag like "<", "<t", "<T", etc.
                                # Check last few chars
                                partial_tag = False
                                # Check typical starting chars of <thought> or <function
                                last_chars = buffer[-10:].lower() if len(buffer) > 10 else buffer.lower()
                                if "<" in last_chars:
                                    # If "<" is present, check if it could be start of <thought> or <function
                                    # We wait for more content if it looks like a tag start
                                    potential_tags = ["<thought>", "<function"]
                                    for tag in potential_tags:
                                        # Check if buffer ends with a prefix of 'tag'
                                        # e.g. ends with "<t", "<th", "<tho"
                                        # We compare against the start of the tag
                                        # But we only care if the "<" is recent.
                                        # Find index of "<"
                                        less_pos = last_chars.rfind("<")
                                        if less_pos != -1:
                                            suffix = last_chars[less_pos:]
                                            # Only wait if suffix is 2+ chars (< + letter), not just <
                                            if tag.startswith(suffix) and len(suffix) >= 2:
                                                partial_tag = True
                                                break
                                
                                if partial_tag:
                                    break # Wait for more chunks

                                if "<function" in buffer.lower():
                                     # Drop function tags aggressively
                                     match_func = re.search(r'<function.*?>', buffer, re.IGNORECASE | re.DOTALL)
                                     if match_func:
                                         buffer = buffer[match_func.end():]
                                         continue
                                     else:
                                         # Wait for closing >
                                         break
                                else:
                                    # Emit visible tokens more aggressively
                                    # If there's a < in buffer, emit everything before it to reduce lag
                                    less_pos = buffer.rfind("<")
                                    if less_pos > 0:
                                        # Emit safe content before <, keep potential tag in buffer
                                        yield self._format_event(StreamEventType.TOKEN, {
                                            "content": buffer[:less_pos]
                                        })
                                        buffer = buffer[less_pos:]
                                    elif less_pos == -1:
                                        # No < at all, emit everything
                                        yield self._format_event(StreamEventType.TOKEN, {
                                            "content": buffer
                                        })
                                        buffer = ""
                                    # If less_pos == 0, buffer starts with <, wait for more to determine if tag
                                    break

                            if in_thought_block:
                                # Look for close tag (case-insensitive)
                                match_end = re.search(r'</thought>', buffer, re.IGNORECASE)
                                if match_end:
                                    thought_content = buffer[:match_end.start()]
                                    buffer = buffer[match_end.end():]
                                    in_thought_block = False
                                    
                                    if thought_content.strip():
                                        parts = thought_content.split("\n\n")
                                        for part in parts:
                                            if part.strip():
                                                yield self._format_event(StreamEventType.THOUGHT, {
                                                    "phase": "analyzing",
                                                    "content": part.strip()
                                                })
                                    continue
                                else:
                                    # Support streaming thoughts
                                    # Emit more frequently to reduce lag (on newline, period, or length)
                                    should_emit = False
                                    split_idx = -1
                                    
                                    if "\n" in buffer:
                                        split_idx = buffer.find("\n")
                                    elif ". " in buffer: # Space ensures we don't split "e.g." too aggressively
                                        split_idx = buffer.find(". ")
                                    elif len(buffer) > 100:
                                        # Force emit if too long
                                        split_idx = 99
                                        
                                    if split_idx != -1:
                                        to_emit = buffer[:split_idx + 1] # Include the delimiter
                                        buffer = buffer[split_idx + 1:]
                                        
                                        if to_emit.strip():
                                            yield self._format_event(StreamEventType.THOUGHT, {
                                                "phase": "analyzing",
                                                "content": to_emit
                                            })
                                    break

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    display_name = TOOL_NAMES.get(tool_name, tool_name)
                    
                    thought_content = f"**Executing Action**\nI will use {display_name}..."
                    if tool_name == "query_recommendations":
                        bank = tool_input.get('bank') or 'all banks'
                        asset = tool_input.get('asset_class') or 'assets'
                        thought_content = f"**Executing Action**\nQuerying {display_name} for {bank} {asset} recommendations..."
                    elif tool_name == "search_knowledge_base":
                        query = tool_input.get('query') or 'extracted info'
                        thought_content = f"**Executing Action**\nSearching {display_name} for: '{query}'..."
                    elif tool_name == "web_search":
                        query = tool_input.get('query') or 'news'
                        thought_content = f"**Executing Action**\nSearching {display_name} for: '{query}'..."
                        
                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "searching",
                        "content": thought_content,
                        "details": [{"tool": tool_name, "args": json.dumps(tool_input)}]
                    })
                
                elif kind == "on_tool_end":
                    # Parse output for sources
                    output = event["data"].get("output")
                    if output:
                        try:
                            data = json.loads(output)
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and "metadata" in item:
                                        collected_sources.append(item)
                        except json.JSONDecodeError:
                            pass

                elif kind == "on_chain_end" and event["name"] == "AgentExecutor":
                    result = event["data"].get("output")
                    if result and isinstance(result, dict) and "output" in result:
                        final_answer = result["output"]
                        clean_answer = re.sub(r'<thought>.*?</thought>', '', final_answer, flags=re.DOTALL | re.IGNORECASE).strip()

                        yield self._format_event(StreamEventType.COMPLETE, {
                            "answer": clean_answer,
                            "sources": collected_sources,
                            "recommendations": []
                        })
            
        except Exception as e:
            logger.error(f"LangChain Orchestrator error: {e}", exc_info=True)
            yield self._format_event(StreamEventType.ERROR, {
                "message": f"I encountered an error processing your request: {str(e)}"
            })
        finally:
            if search_filter_token is not None:
                reset_search_filter_scope(search_filter_token)
                    


    def _format_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format data as SSE string."""
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

# Singleton
_orchestrator: Optional[AgentOrchestrator] = None

def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
