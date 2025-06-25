from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from subprocess import run, PIPE
import httpx
import os
import fnmatch
import json

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

OLLAMA_URL = "http://localhost:11434/api/generate"
ALLOWED_TARGETS_FILE = os.path.join(os.path.dirname(__file__), "allowed_make_targets.json")

# === 🔍 FILE SEARCH ===
@app.get("/search")
def search_files(
    q: str = Query(default="*"),
    path: str = Query(default="."),
    exts: str = Query(default="pdf,svg,txt,jpg,png")
):
    matched_files = []
    extensions = exts.split(",")

    for root, _, files in os.walk(path):
        for ext in extensions:
            for filename in fnmatch.filter(files, f"*{q}*.{ext.strip()}"):
                full_path = os.path.join(root, filename)
                matched_files.append(full_path)

    return {"files": matched_files}

# === 💬 OLLAMA COMMUNICATION ===
@app.post("/llm")
async def ask_llm(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    model = data.get("model", "llama3")

    payload = {"model": model, "prompt": prompt, "stream": False}

    async with httpx.AsyncClient() as client:
        response = await client.post(OLLAMA_URL, json=payload, timeout=60)
        result = response.json()

    return JSONResponse(content={"response": result.get("response", "")})

# === ⚙️ SAFE MAKE INVOCATION ===
@app.post("/make")
async def run_make(request: Request):
    data = await request.json()
    make_path = data.get("path", "")
    target = data.get("target", "")

    if not os.path.isdir(make_path):
        return JSONResponse(status_code=400, content={"error": "Invalid path"})

    # Load allowed targets
    with open(ALLOWED_TARGETS_FILE) as f:
        allowed = json.load(f).get("targets", [])

    if target not in allowed:
        return JSONResponse(status_code=403, content={"error": f"Target '{target}' not allowed"})

    # Execute make
    result = run(["make", target], cwd=make_path, stdout=PIPE, stderr=PIPE, text=True)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }

# Root endpoint
@app.get("/")
async def read_root():
    return {"message": "MCP Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
