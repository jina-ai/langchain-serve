
```bash
curl --X POST 'http://localhost:8080/ask' \
--header 'Content-Type: application/json' \
--data-raw '{
    "urls": [
        "https://uiic.co.in/sites/default/files/uploads/downloadcenter/Arogya%20Sanjeevani%20Policy%20CIS_2.pdf",
        "https://uiic.co.in/sites/default/files/uploads/downloadcenter/Individual%20Health%20Insurance%20Policy%20CIS_0.pdf"
    ],
    "question": "Inme se kaunse scheme mai waiting period sabse best hai??",
    "envs": {
        "OPENAI_API_KEY": "sk-***"
    }
}'
```