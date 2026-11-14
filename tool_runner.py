from abc import abstractmethod

from dify_plugin import Tool

from cormak import CormakClient, CormakError


class CormakTool(Tool):
    @staticmethod
    @abstractmethod
    def operation(client, params):
        raise NotImplementedError

    def _invoke(self, tool_parameters):
        try:
            with CormakClient(self.runtime.credentials.get("access_token")) as client:
                result = self.operation(client, tool_parameters)
        except CormakError as error:
            raise ValueError(str(error)) from None
        yield self.create_variable_message("result", result)
        yield self.create_json_message(result)
