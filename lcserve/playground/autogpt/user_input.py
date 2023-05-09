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
    name: str
    role: str
    goals: List[str]
    predefined_tools: PredefinedTools
    custom_tools: List[CustomTool]
    endpoint: str = 'autogpt'
    human_in_the_loop: bool = False
    envs: Dict[str, str] = {}


def prompt_user() -> UserInput:
    # Get host
    host = Prompt.ask("🌎 Enter host (e.g. wss://autogpt-bcd407883c.wolf.jina.ai)")

    # Check if host is provided, else exit
    if not host:
        print(
            "Deploy your own autogpt using `lc-serve deploy autogpt` and then run this app again."
        )
        exit()

    # Get goals
    goals = []
    while True:
        if len(goals) == 0:
            goal = Prompt.ask("🧠 Enter goal: (e.g. Solve world hunger)")
        else:
            goal = Prompt.ask("🔧 Enter more goals (if required)")
        if goal:
            goals.append(goal)
        else:
            break

    # Check if goals is provided, else exit
    if not goals:
        print("Please provide 1 or more goals.")
        exit()

    # Get the bot name
    bot_name = Prompt.ask("🤖 Enter bot name (e.g. Autogpt)", default="Tom")

    # Get the bot role
    bot_role = Prompt.ask("🤖 Enter bot role (e.g. Assistant)", default="Assistant")

    # Ask if human feedback is required
    human_in_the_loop = Prompt.ask(
        "🤖 Do you want to enable human feedback?", default="n", choices=["y", "n"]
    )
    human_in_the_loop = human_in_the_loop.lower() == "y"

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
            create_tool = Prompt.ask(
                "🔧 Add a custom tool?", default="y", choices=["y", "n"]
            )
        else:
            create_tool = Prompt.ask(
                "🔧 More custom tools to add?", default="n", choices=["y", "n"]
            )

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
            add_env = Prompt.ask(
                "💻 Add an environment variable?", default="y", choices=["y", "n"]
            )
        else:
            add_env = Prompt.ask(
                "💻 More environment variables?", default="n", choices=["y", "n"]
            )

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
            "name": bot_name,
            "role": bot_role,
            "goals": goals,
            "predefined_tools": {
                "names": predefined_tools_names_list,
                "params": predefined_tools_params_dict,
            },
            "custom_tools": custom_tools_selected,
            "human_in_the_loop": human_in_the_loop,
            "envs": envs_selected,
        }
    )
