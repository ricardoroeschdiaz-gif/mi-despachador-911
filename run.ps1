cd dispatch_mvp
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
start-process -NoNewWindow -FilePath ".\venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--reload"