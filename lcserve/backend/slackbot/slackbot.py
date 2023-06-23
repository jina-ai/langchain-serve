import json
import os
from functools import lru_cache
from typing import Any, Dict, Generator, List, Tuple, Union
from urllib.parse import urlparse

from jina.logging.logger import JinaLogger
from langchain.agents import ConversationalAgent
from langchain.memory import ChatMessageHistory
from langchain.output_parsers import StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema import ChatMessage
from langchain.tools import StructuredTool
from langchain.tools.base import ToolException
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tenacity import retry, stop_after_attempt, wait_exponential

PROGRESS_MESSAGE = "Processing..."


class SlackBot:
    _logger = JinaLogger('SlackBot')

    def __init__(self, workspace: str):
        from langchain.output_parsers import PydanticOutputParser
        from slack_bolt import App
        from slack_bolt.adapter.fastapi import SlackRequestHandler

        try:
            from helper import TextOrBlock
        except ImportError:
            from .helper import TextOrBlock

        self.slack_app = App()
        self.workspace = workspace
        self.handler = SlackRequestHandler(self.slack_app)
        self._parser = PydanticOutputParser(pydantic_object=TextOrBlock)

    @staticmethod
    def slack_client() -> WebClient:
        return WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))

    @staticmethod
    def get_username(userid: str) -> str:
        try:
            response = SlackBot.slack_client().users_profile_get(user=userid)
            return response.data['profile']['real_name']
        except Exception as e:
            return None

    @classmethod
    def extract_channel_ts(cls, url):
        try:
            parsed_url = urlparse(url)
            if not all([parsed_url.scheme, parsed_url.netloc, parsed_url.path]):
                return None, None

            path_parts: List[str] = parsed_url.path.split('/')
            if len(path_parts) != 4:
                return None, None

            channel_id = path_parts[2]
            thread_ts = (
                path_parts[3].replace('p', '', 1)[:10]
                + '.'
                + path_parts[3].replace('p', '', 1)[10:]
            )

            return channel_id, thread_ts

        except Exception as e:
            cls._logger.error(f"Error extracting channel and ts from url: {e}")
            return None, None

    @classmethod
    def get_history(cls, channel: str, ts: str) -> ChatMessageHistory:
        cls._logger.debug(f"Getting history for {channel} {ts}")

        response = cls.slack_client().conversations_replies(channel=channel, ts=ts)
        msgs: List[Dict] = response["messages"]
        history = ChatMessageHistory()

        def _extract_text_from_blocks(user: str, blocks: Union[List, Dict]):
            if isinstance(blocks, dict):
                for key, value in blocks.items():
                    if key == 'text' and isinstance(value, dict):
                        history.add_message(
                            ChatMessage(
                                content=value['text'],
                                role=user,
                                additional_kwargs={"id": user},
                            )
                        )
                    elif key == 'text' and isinstance(value, str):
                        history.add_message(
                            ChatMessage(
                                content=value,
                                role=user,
                                additional_kwargs={"id": user},
                            )
                        )
                    else:
                        _extract_text_from_blocks(user=user, blocks=value)

            elif isinstance(blocks, list):
                for item in blocks:
                    _extract_text_from_blocks(user=user, blocks=item)

        # read all but the last message
        for msg in msgs[:-1]:
            if msg.get("type") != "message":
                # TODO: not sure how to handle this
                continue

            if 'blocks' in msg:
                if 'user' in msg:
                    username = SlackBot.get_username(msg['user']) or msg['user']
                    user = f"Human ({username})"
                elif 'bot_id' in msg:
                    user = msg['bot_id']

                _extract_text_from_blocks(user=user, blocks=msg['blocks'])

            text: str = msg.get("text")
            if 'bot_id' in msg:
                if text.strip() in ("", PROGRESS_MESSAGE):
                    continue

                history.add_message(
                    ChatMessage(
                        content=text, role="AI", additional_kwargs={"id": msg["bot_id"]}
                    )
                )
            elif 'user' in msg:
                username = SlackBot.get_username(msg['user']) or msg['user']
                history.add_message(
                    ChatMessage(
                        content=text,
                        role=f"Human ({username})",
                    )
                )

        return history

    @classmethod
    def slack_messages(cls, url: str) -> str:
        """\
Get chat messages from an existing slack conversation url. \
It is important to note that this URL should already be present in the conversation history, in the format `https://<workspace>.slack.com/archives/<channel_id>/<thread_ts>`. \
You are not permitted to generate or make up these URLs. \
If you can't find the url, please ask the user to provide it to you.
"""

        cls._logger.debug(f"Getting slack messages from {url}")

        if url.startswith('url='):
            url = url[4:]
        # if url is wrapped with '' or "" or <>, remove them
        if url.startswith("'") and url.endswith("'"):
            url = url[1:-1]
        elif url.startswith('"') and url.endswith('"'):
            url = url[1:-1]
        elif url.startswith('<') and url.endswith('>'):
            url = url[1:-1]

        channel, ts = SlackBot.extract_channel_ts(url)
        if channel is None or ts is None:
            raise ToolException(
                f"Invalid URL `{url}` received, could not extract channel and ts"
            )

        try:
            history = SlackBot.get_history(channel, ts)
        except Exception as e:
            _err_msg = (
                f"Invalid URL `{url}` received, could not extract channel and ts as {e}"
            )
            if isinstance(e, SlackApiError):
                if e.response["error"] == "not_in_channel":
                    _err_msg = f"Cannot access the channel `{channel}`. Please add me to the channel and try again."
                elif e.response["error"] == "channel_not_found":
                    _err_msg = f"Channel `{channel}` was not found. Please check the URL and try again."
                elif e.response["error"] == "thread_not_found":
                    _err_msg = f"Thread `{ts}` was not found. Please check the URL and try again."

            raise ToolException(_err_msg)

        return json.dumps([{msg.role: msg.content} for msg in history.messages])

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    def send_message(
        client: WebClient,
        channel: str,
        ts: str,
        text: str = None,
        blocks: List[Dict] = None,
    ) -> Tuple[str, str]:
        if text is not None:
            response = client.chat_postMessage(channel=channel, thread_ts=ts, text=text)
        elif blocks is not None:
            response = client.chat_postMessage(
                channel=channel, thread_ts=ts, blocks=blocks
            )
        else:
            raise ValueError("Either text or blocks must be specified")
        return response["channel"], response["ts"]

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    def update_message(
        client: WebClient,
        channel: str,
        ts: str,
        text: str = None,
        blocks: List[Dict] = None,
    ):
        if text is not None:
            client.chat_update(channel=channel, ts=ts, text=text)
        elif blocks is not None:
            client.chat_update(channel=channel, ts=ts, text=text, blocks=blocks)
        else:
            raise ValueError("Either text or blocks must be specified")

    @staticmethod
    def send(
        client: WebClient,
        channel: str,
        thread_ts: str,
        parser: StructuredOutputParser,
        progress_message: str = PROGRESS_MESSAGE,
    ):
        try:
            from helper import TextOrBlock
        except ImportError:
            from .helper import TextOrBlock

        # send a progress message first on the thread
        channel, ts = SlackBot.send_message(
            client, channel, thread_ts, progress_message
        )

        def __call__(text: Union[str, Generator[str, None, None]]):
            message_text = ""

            if isinstance(text, Generator):
                for i, t in enumerate(text):
                    message_text += t
                    SlackBot.update_message(client, channel, ts, message_text)
            else:
                try:
                    textOrBlock: TextOrBlock = parser.parse(text)
                except Exception as e:
                    SlackBot.update_message(client, channel, ts, text=text)
                    return

                if textOrBlock.kind == "text":
                    SlackBot.update_message(
                        client=client,
                        channel=channel,
                        ts=ts,
                        text=textOrBlock.text,
                    )
                elif textOrBlock.kind == "block":
                    SlackBot.update_message(
                        client=client,
                        channel=channel,
                        ts=ts,
                        text="Answer:",
                        blocks=[b.dict() for b in textOrBlock.blocks],
                    )

        return __call__

    @classmethod
    @lru_cache
    def get_slack_url(cls):
        response = cls.slack_client().auth_test()
        return response["url"]

    @lru_cache(maxsize=128)
    def is_bot_in_channel(self, client: WebClient, channel: str) -> bool:
        try:
            bot_id = client.auth_test()["user_id"]
            response = client.conversations_members(channel=channel)
            return bot_id in response["members"]

        except SlackApiError as e:
            self._logger.error(f"Error while checking if bot is in channel {e}")
            return False

    @staticmethod
    def get_agent_tools() -> List[StructuredTool]:
        return [
            StructuredTool.from_function(
                func=SlackBot.slack_messages,
                handle_tool_error=True,
            )
        ]

    @staticmethod
    def get_agent_prompt() -> PromptTemplate:
        prefix = """
As an AI bot on Slack, your primary objective is to provide substantial assistance to one or more human users within a Slack thread. \
Your mission is to facilitate the completion of tasks through a strategic approach, gathering comprehensive information by posing pertinent questions to refine your understanding of the users' needs. \
Not only should you deliver precise, insightful responses to aid users in task fulfillment, \
but also be proactive in offering innovative solutions and suggestions they may not have considered. \
If a slack url is provided, you can clean it up and pass it to any existing tools. \
If the answer contains `Human (userid)`, replace it with `<@userid>`.

TOOLS:
------

Assistant has access to the following tools:
        """

        suffix = """Begin!

Previous conversation history:
{chat_history}

Human: {input}
{agent_scratchpad}"""

        return ConversationalAgent.create_prompt(
            tools=SlackBot.get_agent_tools(),
            prefix=prefix,
            suffix=suffix,
        )

    def app_mention(self, func):
        @self.slack_app.event('app_mention')
        def wrapper(client: WebClient, body, context):
            _event: Dict = body["event"]
            _channel = _event["channel"]
            _thread_ts = _event.get("thread_ts", _event["ts"])
            _user = _event["user"]
            if "text" in _event:
                _message = _event["text"]
            elif "message" in _event:
                _message = _event["message"]["text"]
                _thread_ts = _event["message"].get("ts", _thread_ts)

            self._logger.info(
                f"App mentioned by user `{_user}` in channel `{_channel}`. Message: `{_message}` "
            )

            if not self.is_bot_in_channel(client, _channel):
                # send a DM to the user to invite the bot to the channel
                client.chat_postMessage(
                    channel=_user,
                    text=f"Unfortunately, I'm not in the channel (ID: {_channel}), you mentioned me in. Please invite me there and try again.",
                )
                return

            func(
                message=_message,
                prompt=SlackBot.get_agent_prompt(),
                history=SlackBot.get_history(_channel, _thread_ts),
                tools=SlackBot.get_agent_tools(),
                reply=SlackBot.send(
                    client=client,
                    channel=_channel,
                    thread_ts=_thread_ts,
                    parser=self._parser,
                ),
                workspace=self.workspace,
                user=_user,
                context=context,
            )

        return wrapper

    def message(self, func):
        @self.slack_app.event('message')
        def wrapper(client, body, context):
            _event: Dict = body["event"]
            _channel = _event["channel"]
            _thread_ts = _event.get("thread_ts", _event["ts"])

            if "text" in _event:
                _message = _event["text"]
            elif "message" in _event:
                _message = _event["message"]["text"]
                _thread_ts = _event["message"].get("ts", _thread_ts)

            self._logger.info(
                f"DM received in channel `{_channel}`. Message: `{_message}` "
            )

            func(
                message=_message,
                prompt=SlackBot.get_agent_prompt(),
                history=SlackBot.get_history(_channel, _thread_ts),
                tools=SlackBot.get_agent_tools(),
                reply=SlackBot.send(
                    client=client,
                    channel=_channel,
                    thread_ts=_thread_ts,
                    parser=self._parser,
                ),
                workspace=self.workspace,
                user=_channel,
                context=context,
            )

        return wrapper

    def register(self, func) -> Any:
        self.app_mention(func)
        self.message(func)
        return func
