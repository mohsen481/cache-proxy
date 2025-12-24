from fastapi import FastAPI, Request

app = FastAPI()

@app.get('/')
def show_origin(request: Request):
    origin = getattr(app.state, "origin", "not set")
    return {origin}

