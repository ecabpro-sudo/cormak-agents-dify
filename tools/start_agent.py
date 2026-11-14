from operations import start_agent
import tool_runner


class StartAgentTool(tool_runner.CormakTool):
    operation = staticmethod(start_agent)
