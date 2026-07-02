"""
Agent orchestrator using LangChain and Mistral.

This module handles:
- Tool-calling workflow for query interpretation
- Tool selection and execution (RAG, SQL, Web) using LangChain
- Response generation with code-owned execution traces
"""
import logging
import json
import re
from typing import Optional, Dict, Any, AsyncGenerator

from langchain_openai import ChatOpenAI

from config.settings import settings
from services.tools import AVAILABLE_TOOLS, reset_search_filter_scope, set_search_filter_scope
from models.schemas import ChatRequest, StreamEventType

logger = logging.getLogger(__name__)

TOOL_DISPLAY_NAMES = {
    "query_internal_views": "Internal Investment Database",
    "get_analyst_intelligence": "Analyst Intelligence",
    "search_knowledge_base": "Research Report Knowledge Base",
    "web_search": "Live Web Search",
}


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
    
    async def process_query(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Process a user query using LangChain's AgentExecutor.
        Yields SSE events: thought, token, complete, error.
        """
        search_filter_token = None
        
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate
            from services.prompt_loader import load_prompt
            
            # Load system prompt from markdown file
            system_prompt = load_prompt("agent_system")
            
            # Define prompt for tool-calling execution.
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # Create Agent
            agent = create_tool_calling_agent(self.llm, AVAILABLE_TOOLS, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=AVAILABLE_TOOLS, verbose=True)

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
                        visible_content = self._strip_private_markup(content)
                        if visible_content:
                            yield self._format_event(StreamEventType.TOKEN, {
                                "content": visible_content
                            })

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    thought_content = self._build_tool_start_trace(tool_name, tool_input)
                        
                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "searching",
                        "content": thought_content,
                        "details": [{"tool": tool_name, "args": json.dumps(tool_input)}]
                    })
                
                elif kind == "on_tool_end":
                    # Parse output for sources
                    tool_name = event["name"]
                    output = event["data"].get("output")
                    source_count = 0
                    if output:
                        try:
                            data = json.loads(output)
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and "metadata" in item:
                                        collected_sources.append(item)
                                        source_count += 1
                        except json.JSONDecodeError:
                            pass
                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "analyzing",
                        "content": self._build_tool_end_trace(tool_name, source_count),
                        "details": [{"tool": tool_name, "source_count": source_count}]
                    })

                elif kind == "on_chain_end" and event["name"] == "AgentExecutor":
                    result = event["data"].get("output")
                    if result and isinstance(result, dict) and "output" in result:
                        final_answer = result["output"]
                        clean_answer = self._strip_private_markup(final_answer).strip()

                        yield self._format_event(StreamEventType.THOUGHT, {
                            "phase": "generating",
                            "content": "Synthesizing answer."
                        })

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

    def _strip_private_markup(self, content: str) -> str:
        """Remove private/planning markup if a model emits it despite the prompt."""
        content = re.sub(
            r"<thought>.*?</thought>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        content = re.sub(r"</?thought>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<function.*?>", "", content, flags=re.DOTALL | re.IGNORECASE)
        return content

    def _build_tool_start_trace(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)

        if tool_name == "search_knowledge_base":
            query = tool_input.get("query") or "the requested report context"
            return f"Searching {display_name} for: '{query}'."

        if tool_name == "query_internal_views":
            asset = tool_input.get("asset_class") or "all asset classes"
            return f"Querying {display_name} for {asset} views."

        if tool_name == "get_analyst_intelligence":
            analyst = tool_input.get("analyst_name")
            sector = tool_input.get("sector")
            target = analyst or sector or "matching analysts"
            return f"Looking up {display_name} for {target}."

        if tool_name == "web_search":
            query = tool_input.get("query") or "market context"
            return f"Searching {display_name} for: '{query}'."

        return f"Running {display_name}."

    def _build_tool_end_trace(self, tool_name: str, source_count: int) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        if source_count == 1:
            return f"Found 1 source from {display_name}."
        if source_count > 1:
            return f"Found {source_count} sources from {display_name}."
        return f"Finished {display_name}."

# Singleton
_orchestrator: Optional[AgentOrchestrator] = None

def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
