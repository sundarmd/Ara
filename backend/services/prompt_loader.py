"""
Prompt Loader Service.

Responsible for loading markdown prompt templates from the file system.
Supporting "Prompt Engineering as Code".
"""
import os
import logging
from typing import Dict, Any

from config.settings import settings

logger = logging.getLogger(__name__)

# Directory where prompts are stored
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

class PromptLoader:
    """
    Loads and caches prompt templates from markdown files.
    """
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def load(cls, prompt_name: str, **kwargs) -> str:
        """
        Load a prompt by name (filename without extension).
        Optionally format it with kwargs.
        
        Args:
            prompt_name: Name of the prompt file (e.g. 'agent_system')
            **kwargs: Variables to inject into the template (e.g. bank="JPM")
            
        Returns:
            The loaded (and formatted) prompt string.
        """
        if prompt_name not in cls._cache:
            file_path = os.path.join(PROMPTS_DIR, f"{prompt_name}.md")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    cls._cache[prompt_name] = content
            except FileNotFoundError:
                logger.error(f"Prompt file not found: {file_path}")
                raise ValueError(f"Prompt '{prompt_name}' not found")
        
        template = cls._cache[prompt_name]
        
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                # Be helpful with error messages
                logger.error(f"Missing key for prompt '{prompt_name}': {e}")
                raise ValueError(f"Missing variable for prompt '{prompt_name}': {e}")
                
        return template

    @classmethod
    def clear_cache(cls):
        """Clear the memory cache (useful for hot-reloading during dev)."""
        cls._cache.clear()

def load_prompt(name: str, **kwargs) -> str:
    """Convenience wrapper for PromptLoader.load"""
    return PromptLoader.load(name, **kwargs)
