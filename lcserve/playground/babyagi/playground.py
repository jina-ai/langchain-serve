import os
import asyncio

import aiohttp
import nest_asyncio
from pydantic import BaseModel, ValidationError
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Header, TextLog, Button, Static

from user_input import UserInput, prompt_user


def patch_loop():
    try:
        nest_asyncio.apply()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            nest_asyncio.apply()
        except RuntimeError:
            pass

    return asyncio.get_event_loop()


loop = patch_loop()

(
    cot_queue,
    task_details_queue,
    task_result_queue,
    human_prompt_question_queue,
    human_prompt_answer_queue,
) = (
    asyncio.Queue(),
    asyncio.Queue(),
    asyncio.Queue(),
    asyncio.Queue(),
    asyncio.Queue(),
)


class CoTResponse(BaseModel):
    result: str
    error: str
    stdout: str


class TaskDetailsResponse(BaseModel):
    id: str
    name: str
    current: bool = False


class TaskResultResponse(BaseModel):
    id: str
    name: str
    result: str


class HumanPrompt(BaseModel):
    prompt: str


async def talk_to_agent(user_input: UserInput):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f'{user_input.host}/{user_input.endpoint}') as ws:
            log.info(f'Connected to {user_input.host}/{user_input.endpoint}')
            log.info(f'📤 {user_input.json(exclude={"host", "endpoint"})}')
            await ws.send_json(user_input.dict(exclude={'host', 'endpoint'}))
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await ws.close()
                        break
                    else:
                        try:
                            response = CoTResponse.parse_raw(msg.data)
                            log.info(f'📥 {response.json()}')
                            text = None
                            if response.result:
                                text = response.result
                            if response.stdout:
                                text = response.stdout
                            if response.error:
                                text = response.error

                            if text:
                                await cot_queue.put(text)
                                continue

                        except ValidationError:
                            try:
                                task_details = TaskDetailsResponse.parse_raw(msg.data)
                                log.info(f'📥 {task_details.json()}')
                                await task_details_queue.put(task_details)
                                continue
                            except ValidationError:
                                try:
                                    task_result = TaskResultResponse.parse_raw(msg.data)
                                    log.info(f'📥 {task_result.json()}')
                                    await task_result_queue.put(task_result)
                                    continue
                                except ValidationError as e:
                                    try:
                                        prompt = HumanPrompt.parse_raw(msg.data)
                                        log.info(f'📥 {prompt.json()}')
                                        await human_prompt_question_queue.put(prompt)
                                        answer = await human_prompt_answer_queue.get()
                                        await ws.send_str(answer)
                                        continue
                                    except ValidationError:
                                        log.info(f'Unknown message: {msg.data}')

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.info('ws connection closed with exception %s' % ws.exception())
                else:
                    log.info(msg)


class ChainOfThoughts(Horizontal):
    def __init__(self, title: str, cot_queue: asyncio.Queue, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._cot_queue = cot_queue
        self._all_content = ''

    async def _read_cot(self):
        while True:
            item = await self._cot_queue.get()
            self._cot_queue.task_done()
            self._all_content += item
            self.text_log.clear()
            self.text_log.write(self._all_content, expand=False)

    async def on_mount(self):
        asyncio.create_task(self._read_cot())

    def _init_text_log(self) -> TextLog:
        self.text_log = TextLog(wrap=True)
        return self.text_log

    def compose(self) -> ComposeResult:
        yield self._init_text_log()


class TasksTable(Horizontal):
    def __init__(self, title: str, task_queue: asyncio.Queue, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._task_queue = task_queue

    async def _read_tasks(self):
        while True:
            task: TaskDetailsResponse = await self._task_queue.get()
            self._task_queue.task_done()
            _key = f'{task.id}-{task.name}'
            if _key not in self.dt.rows:
                self.dt.add_row(task.id, task.name, task.current, key=_key)

    async def on_mount(self):
        asyncio.create_task(self._read_tasks())

    def _init_dt(self) -> DataTable:
        self.dt = DataTable()
        self.dt.zebra_stripes = True
        self.dt.cursor_type = "row"
        self.dt.add_column("Task ID ", width=10)
        self.dt.add_column("Description")
        self.dt.add_column("Currently Executing?")
        return self.dt

    def compose(self) -> ComposeResult:
        yield self._init_dt()


class ShouldContinue(Static):
    def __init__(
        self,
        human_prompt_question_queue: asyncio.Queue,
        human_prompt_answer_queue: asyncio.Queue,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._human_prompt_question_queue = human_prompt_question_queue
        self._human_prompt_answer_queue = human_prompt_answer_queue

    async def _read_prompt(self):
        while True:
            await self._human_prompt_question_queue.get()
            self._human_prompt_question_queue.task_done()
            self._yes.disabled = False
            self._no.disabled = False
            self._yes.variant = 'primary'
            self._no.variant = 'primary'

    async def _send_answer(self, answer: str):
        log.info(f'📤 {answer}')
        await self._human_prompt_answer_queue.put(answer)
        self._yes.disabled = True
        self._no.disabled = True
        self._yes.variant = 'default'
        self._no.variant = 'default'

    async def on_mount(self):
        asyncio.create_task(self._read_prompt())

    def compose(self) -> ComposeResult:
        self._exit = Button("Exit", classes='box')
        self._yes = Button('Continue? (yes)', disabled=True, classes='box')
        self._no = Button('Continue? (no)', disabled=True, classes='box')
        yield self._yes
        yield self._no
        yield self._exit


class BabyAGIPlayground(App[None]):
    CSS = """
    DataTable {
        height: 1.2fr;
        border: round blue;
        background: $boost;
        align: center middle;
        content-align: center middle;
    }

    .tasks {
        align: center middle;
        height: 1.2fr;
    }

    .cot {
        height: 0.8fr;
        border: round green;
    }

    .box {
        height: 100%;
        border: solid green;
    }

    #sidebar {
        dock: bottom;
        layout: grid;
        height: 0.05fr;
        color: #0f2b41;
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
        text-style: bold;
    }
    """

    TITLE = "BabyAGI"
    SUB_TITLE = "A playground"

    def compose(self) -> ComposeResult:
        self.should_continue = ShouldContinue(
            human_prompt_question_queue=human_prompt_question_queue,
            human_prompt_answer_queue=human_prompt_answer_queue,
            id="sidebar",
        )
        yield self.should_continue
        yield Header()
        yield TasksTable("Tasks Table", task_queue=task_details_queue, classes="tasks")
        yield ChainOfThoughts("Chain of Thoughts", cot_queue=cot_queue, classes="cot")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if str(event.button.label) == 'Continue? (yes)':
            asyncio.run(self.should_continue._send_answer('y'))
        elif str(event.button.label) == 'Continue? (no)':
            asyncio.run(self.should_continue._send_answer('n'))
            self.exit()
        elif str(event.button.label) == 'Exit':
            self.exit()


def play(verbose: bool = False):
    user_input = prompt_user()
    if verbose:
        os.environ['TEXTUAL'] = 'devtools'
    task = loop.create_task(talk_to_agent(user_input))
    try:
        BabyAGIPlayground().run()
    except KeyboardInterrupt:
        task.cancel()


if __name__ == "__main__":
    play(verbose=False)
