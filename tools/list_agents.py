from operations import list_agents
import tool_runner


class ListAgentsTool(tool_runner.CormakTool):
    operation = staticmethod(list_agents)
