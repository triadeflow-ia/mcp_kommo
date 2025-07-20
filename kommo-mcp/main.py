from fastapi import FastAPI
from tools.list_leads import list_leads
import uvicorn

app = FastAPI()

@app.get("/tools/list_leads")
def get_leads():
    return list_leads()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
