from operations import product_copy
import tool_runner


class ProductCopyTool(tool_runner.CormakTool):
    operation = staticmethod(product_copy)
