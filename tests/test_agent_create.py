import unittest

from infrastructure.ai import LLMClientFactory, create_react_agent
from infrastructure.config import LLMConfig

system_prompt = "你是一名java工程师，熟练掌握数据结构，算法，java语法。"
user_prompt = "帮我写一个快排算法"

class TestCreateAgent(unittest.TestCase):
    def setUp(self):
        pass

    def test_agent_create(self):
        llm_config = LLMConfig.load()
        client_factory = LLMClientFactory.from_config(llm_config)
        llm = client_factory.create_llm()
        agent = create_react_agent(llm, system_prompt=system_prompt, tools=[])
        message = {
            "messages": [{
                "role": "user",
                "content": user_prompt
            }]
        }
        result = agent.invoke(message, {"configurable": {"thread_id": "test-thread-1"}})
        self.assertIn("messages", result)


