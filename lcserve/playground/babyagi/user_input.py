import os
from typing import Dict, List

from rich.prompt import Prompt
from pydantic import BaseModel


class PredefinedTools(BaseModel):
    names: List[str]
    params: Dict[str, str]


class CustomTool(BaseModel):
    name: str
    prompt: str
    description: str


class UserInput(BaseModel):
    host: str
    objective: str
    first_task: str
    predefined_tools: PredefinedTools
    custom_tools: List[CustomTool]
    endpoint: str = 'baby_agi'
    interactive: bool = True
    envs: Dict[str, str] = {}


def prompt_user() -> UserInput:
    # Get host
    host = Prompt.ask("🌎 Enter host (e.g. wss://babyagi-bcd407883c.wolf.jina.ai)")

    # Check if host is provided, else exit
    if not host:
        print(
            "Deploy your own babyagi using `lc-serve deploy babyagi` and then run this app again."
        )
        exit()

    # Get objective
    objective = Prompt.ask("🧠 Enter objective: (e.g. Solve world hunger)")

    # Check if objective is provided, else exit
    if not objective:
        print("Please provide an objective.")
        exit()

    # Get first task
    first_task = Prompt.ask(
        "1️⃣  Enter first task (Default first task is `Make a list of action items`)",
        default="Make a list of action items",
    )

    # Get the names of predefined tools from user
    predefined_tools_names = Prompt.ask(
        "🧰 Enter predefined tools names (comma separated) (type 'done' when finished)",
        default="wikipedia",
    )
    predefined_tools_names_list = predefined_tools_names.split(",")

    # Get the params for predefined tools from user
    predefined_tools_params = Prompt.ask(
        "🧰 Enter predefined tools params (comma separated) (type 'done' when finished)",
        default="",
    )
    predefined_tools_params = predefined_tools_params.split(",")
    if len(predefined_tools_params) > 1:
        predefined_tools_params_dict = dict(
            [param.split(":") for param in predefined_tools_params]
        )
    else:
        predefined_tools_params_dict = {}

    # Get custom tools
    custom_tools_selected = []
    while True:
        if len(custom_tools_selected) == 0:
            create_tool = Prompt.ask("🔧 Add a custom tool? (y/n)", default="y")
        else:
            create_tool = Prompt.ask("🔧 More custom tools to add? (y/n)", default="n")

        if create_tool.lower() != "y":
            break
        tool_name = Prompt.ask("   Enter tool name", default="TODO")
        tool_prompt = Prompt.ask(
            "   Enter tool prompt",
            default="You are a planner who is an expert at coming up with a todo list for a given objective. Come up with a todo list of just 2 items for this objective: {objective}",
        )
        tool_description = Prompt.ask(
            "   Enter tool description",
            default="useful for when you need to come up with todo lists. Input: an objective to create a todo list for. Output: a todo list for that objective. Please be very clear what the objective is!",
        )
        custom_tools_selected.append(
            {"name": tool_name, "prompt": tool_prompt, "description": tool_description}
        )

    # Get envs
    envs_selected = {}
    while True:
        if len(envs_selected) == 0:
            add_env = Prompt.ask("💻 Add an environment variable? (y/n)", default="y")
        else:
            add_env = Prompt.ask("💻 More environment variables? (y/n)", default="n")

        if add_env.lower() != "y":
            break
        env_name = Prompt.ask("   Enter environment variable name")
        env_value = os.environ.get(env_name)
        if not env_value:
            env_value = Prompt.ask("   Enter environment variable value")
        envs_selected[env_name] = env_value

    return UserInput(
        **{
            "host": host,
            "objective": objective,
            "first_task": first_task,
            "predefined_tools": {
                "names": predefined_tools_names_list,
                "params": predefined_tools_params_dict,
            },
            "custom_tools": custom_tools_selected,
            "envs": envs_selected,
        }
    )
