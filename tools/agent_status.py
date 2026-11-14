from operations import agent_status
import tool_runner


class AgentStatusTool(tool_runner.CormakTool):
    operation = staticmethod(agent_status)
