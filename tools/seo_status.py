from operations import seo_status
import tool_runner


class SeoStatusTool(tool_runner.CormakTool):
    operation = staticmethod(seo_status)
