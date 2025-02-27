from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn





app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/")
def read_root(message:UserMessage):
    return getAnswer(message.sender_id,message.message)


