backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

.\frontend\.venv\Scripts\python.exe -m streamlit run .\frontend\main.py --server.headless true --server.port 8502                 

# If you need the backend tests:
backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v


# supabase commands 

npx.cmd --yes supabase@latest --version
npx.cmd --yes supabase@latest login --token YOUR_SUPABASE_ACCESS_TOKEN --output-format text
npx.cmd --yes supabase@latest link --project-ref YOUR_PROJECT_REF
npx.cmd --yes supabase@latest migration list
npx.cmd --yes supabase@latest db push --dry-run
npx.cmd --yes supabase@latest db push

# Without Docker, run supabase/seed.sql in the linked project's SQL Editor
# after db push. db reset is local-only and requires Docker or Podman.