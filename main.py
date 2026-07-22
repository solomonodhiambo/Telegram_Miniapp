from fastapi import FastAPI

app = FastAPI(
    title="Telegram Mini App API",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Telegram Mini App API"
    }
