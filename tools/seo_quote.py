from operations import seo_quote
import tool_runner


class SeoQuoteTool(tool_runner.CormakTool):
    operation = staticmethod(seo_quote)
