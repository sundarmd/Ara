import unittest

from services.prompt_loader import load_prompt
from services.tools import AVAILABLE_TOOLS


class AgentPromptTests(unittest.TestCase):
    def test_agent_system_prompt_matches_available_tool_names(self):
        prompt = load_prompt("agent_system")
        tool_names = {tool.name for tool in AVAILABLE_TOOLS}

        for tool_name in tool_names:
            self.assertIn(f"`{tool_name}`", prompt)

        self.assertNotIn("`query_recommendations`", prompt)
        self.assertNotIn("bank=None", prompt)

