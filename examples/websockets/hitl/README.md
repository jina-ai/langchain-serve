## Human in the Loop

This directory contains 2 files

##### `hitl.py` 

1. Defines a function `hitl` decorated with `@serving` with `websocket=True`.

https://github.com/jina-ai/langchain-serve/blob/d0726b8e730f4646fd9e54561a7648f9c3b1af60/examples/websockets/hitl/hitl.py#L11-L12

2. Accepts `streaming_handler` from kwargs and passes it to `ChatOpenAI` and `OpenAI` callback managers. This handler is responsible to stream the response to the client.

https://github.com/jina-ai/langchain-serve/blob/9f793f4311007f6cb775e9ac19f89694eb97b80d/examples/websockets/hitl/hitl.py#L19-L22

https://github.com/jina-ai/langchain-serve/blob/9f793f4311007f6cb775e9ac19f89694eb97b80d/examples/websockets/hitl/hitl.py#L27-L30

3. Returns `agent.run` output which is a `str`.

https://github.com/jina-ai/langchain-serve/blob/9f793f4311007f6cb775e9ac19f89694eb97b80d/examples/websockets/hitl/hitl.py#L43

##### `hitl_client.py`

- This is a simple client that connects to the websocket server and sends a `question` to the `hitl` endpoint.
- Listens to the stream of responses and prints it to the console.
- When it receives a response in the format of `{"prompt": "..."}`, it sends the prompt to the user and waits for the user to input the answer. This is how human is brought into the loop.



### Example run on localhost

```bash
python hitl_client.py
```

```text
Connected to ws://localhost:8080/hitl.
I don't know Eric Zhu's birthday, so I need to ask a human.
Action: Human
Action Input: "Do you know Eric Zhu and his birthday?"
Yes
Great, now I can ask for Eric Zhu's birthday.
Action: Human
Action Input: "What is Eric Zhu's birthday?"
29th Feb
I need to make sure this is a valid date.
Action: Calculator
Action Input: Check if 29th Feb is a valid date
```

```python
import datetime

try:
    datetime.datetime(2020, 2, 29)
    print("Valid date")
except ValueError:
    print("Invalid date")
```

```text
I now have a valid birth date, but I need to know the year for Eric's age.
Action: Human
Action Input: "Do you know Eric Zhu's birth year?"
1990
Now I can calculate Eric Zhu's age.
Action: Calculator
Action Input: Current year minus 1990
```

```python
import datetime
print(datetime.datetime.now().year - 1990)
```

```text
I now know Eric Zhu's age.
Final Answer: Eric Zhu's birthday is February 29th, 1990 and he is currently 33 years old.Eric Zhu's birthday is February 29th, 1990 and he is currently 33 years old.% 
```
