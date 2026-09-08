from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
app = FastAPI()
def render(f):
    return open(f, "r", encoding="utf-8").read() if os.path.exists(f) else "<h3>Page not found</h3>"
@app.get("/", response_class=HTMLResponse)
async def r0(): return render("client_login.html")
@app.get("/client_login.html", response_class=HTMLResponse)
async def r1(): return render("client_login.html")
@app.get("/api_auth.html", response_class=HTMLResponse)
async def r2(): return render("api_auth.html")
@app.get("/admin.html", response_class=HTMLResponse)
async def r3(): return render("admin.html")
@app.get("/client_manager.html", response_class=HTMLResponse)
async def r4(): return render("client_manager.html")
@app.get("/mobile.html", response_class=HTMLResponse)
async def r5(): return render("mobile.html")
@app.get("/mobile_client_login.html", response_class=HTMLResponse)
async def r6(): return render("mobile_client_login.html")
@app.get("/mobile_admin.html", response_class=HTMLResponse)
async def r7(): return render("mobile_admin.html")
@app.get("/mobile_client_manager.html", response_class=HTMLResponse)
async def r8(): return render("mobile_client_manager.html")
@app.get("/{filename}", response_class=HTMLResponse)
async def r9(filename: str): return render(filename)
