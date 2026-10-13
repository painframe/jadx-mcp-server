import unittest

from fastmcp import Client

import jadx_mcp_server


class PromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompts_are_discoverable_and_render_current_tools(self):
        async with Client(jadx_mcp_server.mcp) as client:
            self.assertEqual({prompt.name for prompt in await client.list_prompts()},
                             {'analyze_project', 'inspect_methods', 'compare_instances'})
            prompt = await client.get_prompt('inspect_methods', {'class_name': 'example.Class', 'instance': 'candidate'})
            text = '\n'.join(message.content.text for message in prompt.messages)
            self.assertIn('example.Class', text)
            self.assertIn('batch_analysis', text)
            self.assertIn('continuation.next_cursor', text)
            self.assertIn('candidate', text)
