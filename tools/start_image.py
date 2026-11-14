from operations import start_image
import tool_runner


class StartImageTool(tool_runner.CormakTool):
    operation = staticmethod(start_image)
