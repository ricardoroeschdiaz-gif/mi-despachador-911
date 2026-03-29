cd dispatch_mvp
Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
start-process -NoNewWindow -FilePath ".\venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--reload"