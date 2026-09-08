from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "VoidVision Quant Engine Online", "node": "Amsterdam"}
