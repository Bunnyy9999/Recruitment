backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

frontend\.venv\Scripts\python.exe -m streamlit run frontend\main.py --server.port 8502