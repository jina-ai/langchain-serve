### API Endpoints

Jina allows deploying Executors via RESTful/gRPC/WebSocket endpoints. 

#### RESTful Endpoint

##### Python Client

```python
from serve import ServeHTTP, Interact

with ServeHTTP(uses=MyExecutor) as host:
    print(Interact(host, {'question': 'What is 13 raised to the .3432 power?'})) 
```

##### cURL (TBD)

```bash

```


#### gRPC Endpoint

##### Python Client

```python
from serve import ServeGRPC, Interact

with ServeGRPC(uses=MyExecutor) as host:
    print(Interact(host, {'question': 'What is 13 raised to the .3432 power?'})) 
```


##### grpcURL (TBD)

```bash

```

#### WebSocket Endpoint

##### Python Client

```python

from serve import ServeWebSocket, Interact

with ServeWebSocket(uses=MyExecutor) as host:
    print(Interact(host, {'question': 'What is 13 raised to the .3432 power?'}))
```

##### webcocat (TBD)

```bash

```