from operations import media_status
import tool_runner


class MediaStatusTool(tool_runner.CormakTool):
    operation = staticmethod(media_status)
