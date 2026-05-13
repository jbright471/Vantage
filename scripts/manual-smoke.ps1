Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/nodes
Invoke-RestMethod http://127.0.0.1:8000/api/runs
Invoke-WebRequest http://127.0.0.1:8000/api/stream -Headers @{Accept = "text/event-stream"}
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/actions/refresh-node/remote-worker
