```bash
wget -r -A.html https://langchain.readthedocs.io/en/latest/
python ingest.py
```

```bash
uvicorn main:app --reload --port 9000
```