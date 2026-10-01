backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

.\frontend\.venv\Scripts\python.exe -m streamlit run .\frontend\main.py --server.headless true --server.port 8502                 

# If you need the backend tests:
backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v


# supabase commands 

npx --yes supabase@latest --version
npx --yes supabase@latest migration list
npx --yes supabase@latest db push --dry-run
supabase db push