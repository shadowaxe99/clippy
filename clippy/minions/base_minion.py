from dataclasses import dataclass
from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent, AgentOutputParser
from langchain.prompts import StringPromptTemplate
from langchain import LLMChain
from langchain.chat_models import ChatOpenAI
from typing import List, Union
from langchain.schema import AgentAction, AgentFinish
import re


long_warning = 'WARNING: You have been working for a very long time. Please, finish ASAP. ' \
               'If there are obstacles, please, return with the result and explain the situation.'


class CustomOutputParser(AgentOutputParser):
    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        # Check if agent should finish
        if "Final Result:" in llm_output:
            return AgentFinish(
                # Return values is generally always a dictionary with a single `output` key
                # It is not recommended to try anything else at the moment :)
                return_values={"output": llm_output.split("Final Result:")[-1].strip()},
                log=llm_output,
            )
        # Parse out the action and action input
        regex = r"Action\s*\d*\s*:(.*?)\nAction\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        match = re.search(regex, llm_output, re.DOTALL)
        if not match and llm_output.strip().split('\n')[-1].strip().startswith("Thought:"):
            return AgentAction(tool="Python", tool_input='', log=llm_output)
        if not match:
            if 'Action:' in llm_output and 'Action Input:' not in llm_output:
                return AgentAction(tool="Python", tool_input='print("No Action Input specified.")', log=llm_output)
            return AgentAction(tool="Python", tool_input='print("*Continue with thoughts and actions*")',
                               log=llm_output)
        if not match:
            raise ValueError(f"Could not parse LLM output: `{llm_output}`")
        action = match.group(1).strip().strip('`').strip('"').strip("'").strip()
        action_input = match.group(2)
        if '\nThought: ' in action_input or '\nAction: ' in action_input:
            return AgentAction(tool="Python",
                               tool_input='print("Error: Write \'AResult: \' after each '
                                          'action. Execute all the actions without AResult again.")',
                               log=llm_output)
        # Return the action and action input
        return AgentAction(tool=action, tool_input=action_input.strip(" ").strip('"').split('\nThought: ')[0],
                           log=llm_output)


class CustomPromptTemplate(StringPromptTemplate):
    # The template to use
    template: str
    # The list of tools available
    tools: List[Tool]

    def format(self, **kwargs) -> str:
        # Get the intermediate steps (AgentAction, AResult tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps")
        thoughts = ""
        for action, AResult in intermediate_steps:
            thoughts += action.log
            thoughts += f"\nAResult: {AResult}\nThought: "
        # Set the agent_scratchpad variable to that value
        kwargs["agent_scratchpad"] = thoughts
        # Create a tools variable from the list of tools provided
        kwargs["tools"] = "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
        # Create a list of tool names for the tools provided
        kwargs["tool_names"] = ", ".join([tool.name for tool in self.tools])
        result = self.template.format(**kwargs)
        if len(result) > 6000:
            result += '\n' + long_warning + '\n'
        return result


def extract_variable_names(prompt):
    variable_pattern = r"\{(\w+)\}"
    variable_names = re.findall(variable_pattern, prompt)
    for name in ['tools', 'tool_names', 'agent_scratchpad']:
        variable_names.remove(name)
    variable_names.append('intermediate_steps')
    return variable_names


@dataclass
class BaseMinion:
    def __init__(self, base_prompt, avaliable_tools, model: str = 'gpt-4') -> None:
        # llm = ChatOpenAI(temperature=0 if model != 'gpt-3.5-turbo' else 0.7, model_name=model, request_timeout=320)
        llm = ChatOpenAI(temperature=0 if model != 'gpt-3.5-turbo' else 0.7, model_name='gpt-3.5-turbo', request_timeout=320)

        variable_names = extract_variable_names(base_prompt)

        prompt = CustomPromptTemplate(
            template=base_prompt,
            tools=avaliable_tools,
            input_variables=extract_variable_names(base_prompt)
        )

        llm_chain = LLMChain(llm=llm, prompt=prompt)

        output_parser = CustomOutputParser()

        tool_names = [tool.name for tool in avaliable_tools]

        agent = LLMSingleActionAgent(
            llm_chain=llm_chain,
            output_parser=output_parser,
            stop=["AResult:"],
            allowed_tools=tool_names
        )

        self.agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=avaliable_tools, verbose=True)

    def run(self, **kwargs):
        return self.agent_executor.run(**kwargs)
