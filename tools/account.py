from operations import account
import tool_runner


class AccountTool(tool_runner.CormakTool):
    operation = staticmethod(account)
