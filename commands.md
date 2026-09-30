backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

backend\.venv\Scripts\python.exe -m streamlit run frontend\main.py --server.port 8502

# If you need the backend tests:
backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v