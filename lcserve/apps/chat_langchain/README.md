```bash
# only download the index.html
wget -r -A.html https://langchain.readthedocs.io/en/latest/
python ingest.py langchain.readthedocs.io
```

```bash
uvicorn main:app --reload --port 9000
```