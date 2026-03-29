cd dispatch_mvp
.\venv\Scripts\activate
pip install --upgrade pip
pip install --upgrade -r requirements.txt
Stop-Process -Name "uvicorn" -ErrorAction SilentlyContinue
start-process -NoNewWindow -FilePath ".\venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--reload"