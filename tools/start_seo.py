from operations import start_seo
import tool_runner


class StartSeoTool(tool_runner.CormakTool):
    operation = staticmethod(start_seo)
