# ⏱️ Trigger one-time jobs to run asynchronously using `@job` decorator

`langchain-serve` allows you to easily wrap your function to be scheduled asynchronously using the `@serving` decorator. By incorporating this feature, you can effortlessly trigger one-time executions, enhancing the flexibility of your workflow beyond the standard serving APIs.

Let's take a simple example that uses `RetrievalQA` chain to do a question answering based on the file provided.

### 👉 Step 1: Prepare the job function with `@job` decorator

```python
# app.py
import os

import requests
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS

from lcserve import job


@job(timeout=100, backofflimit=3)
def my_job(doc_name: str, question: str):
    print("Starting the job ...")

    url = f"https://raw.githubusercontent.com/langchain-ai/langchain/master/docs/extras/modules/{doc_name}"
    response = requests.get(url)
    data = response.text
    with open("doc.txt", "w") as text_file:
        text_file.write(data)
    print("Download text complete !!")

    embeddings = OpenAIEmbeddings()
    loader = TextLoader("doc.txt", encoding="utf8")
    text_splitter = CharacterTextSplitter()
    docs = text_splitter.split_documents(loader.load())
    faiss_index = FAISS.from_documents(docs, embedding=embeddings)
    faiss_index.save_local(
        folder_path=os.path.dirname(os.path.abspath(__file__)), index_name="index"
    )
    print("Index complete !!")

    llm = ChatOpenAI(temperature=0)
    qa_chain = RetrievalQA.from_chain_type(llm, retriever=faiss_index.as_retriever())
    result = qa_chain({"query": question})

    print(f"\nQuestion: {question}\nAnswer: {result['result']}]\n")
```

In the code, you'll notice the function is adorned with the @job decorator, which accepts two parameters. The first, `timeout`, allows you to set the time limit for the job execution. The second, `backofflimit`, specifies the number of retry attempts allowed before the job is considered as failed.

---

### 👉 Step 2: Create a `requirements.txt` file in your app directory to ensure all necessary dependencies are installed

```text
# requirements.txt
openai
faiss-cpu
```

---

### 👉 Step 3: Run `lc-serve deploy jcloud app` to deploy the app to Jina AI Cloud

We require you deploy the app either through [REST APIs using @serving decorator](../../#-rest-apis-using-serving-decorator) or [Bring your own FastAPI app](../../#-bring-your-own-fastapi-app) first before running any jobs. This step is essential, as the job functionality relies on the existence of the app entity.

You may notice that there is no `OPENAI_API_KEY` explicitly defined in the code. This omission is intentional, and the key won't be necessary if you pass the `secrets.env` file during app deployment. The job will automatically re-use the same set of secrets during its execution.

```bash
lc-serve deploy jcloud app --secret secrets.env
```

```text
# secrets.env
OPENAI_API_KEY=sk-xxx
```

---

### 👉 Step 4: Run `lc-serve job create` to create jobs

After the app deployment is finished (deployed as `langchain-1bde192651`), let's create a job.

```bash
lcserve job create langchain-1bde192651 my_job --params doc_name state_of_the_union.txt --params question 'What did the president say about Ketanji Brown Jackson?'
```

Alternatively you can also create job using the REST API provided.

```bash
curl -X 'POST' \
  'https://langchain-1bde192651.wolf.jina.ai/my_job' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer xxx' \
  -d '{
  "doc_name": "state_of_the_union.txt",
  "question": "What did the president say about Ketanji Brown Jackson?"
}'

```
Where the token used after `Authorization: Bearer` can be found at `~/.jina/config.json`.

You can also list all the jobs triggered or get the details for one given job via CLI.

```bash
lcserve job list langchain-1bde192651
```

```bash
lcserve job get my-job-7787b langchain-1bde192651
```

To access the logs from job executions, refer to the `Job Logs` section of the monitoring dashboard. You can find the link to this dashboard by running:

```bash
lcserve status langchain-1bde192651
```

## 👀 What's next?

- [Learn more about Langchain](https://python.langchain.com/docs/)
- [Learn more about langchain-serve](https://github.com/jina-ai/langchain-serve)
- Have questions? [Join our Discord community](https://discord.jina.ai/)
