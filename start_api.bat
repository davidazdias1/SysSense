@echo off
cd /d C:\PRODSENSE\API
"C:\Users\David Dias\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn api_logger:app --host 127.0.0.1 --port 8000 --reload
