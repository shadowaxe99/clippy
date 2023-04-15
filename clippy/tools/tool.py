from abc import ABC, abstractmethod
from dataclasses import dataclass


class Tool(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def description(self):
        pass

    @abstractmethod
    def run(self, args: str) -> str:
        pass


@dataclass
class Toolkit(Tool):
    name: str
    tools: list[Tool]
    custom_description: str = None

    def description(self):
        return (self.custom_description.strip() or "a toolkit containing the following tools:") + '\n' + \
               "\n".join([f'  - {tool.name}: {tool.description()}' for tool in self.tools])

    def run(self, args: str) -> str:
        tool_name, args = args.split(' ', 1)
        tool = next((tool for tool in self.tools if tool.name == tool_name), None)
        if tool is None:
            return f'error: no tool named "{tool_name}" in toolkit "{self.name}"'
        return tool.run(args)