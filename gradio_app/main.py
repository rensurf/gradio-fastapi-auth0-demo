import json
import os

import gradio as gr
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

app = FastAPI()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith(
        (
            "/assets",
            "/static",
            "/favicon.ico",
            "/file",
            "/fonts",
            "/js",
            "/css",
            "/theme.css",
            "/api",
            "/gradio",
            "/queue",
            "/heartbeat",
            "/callback",
            "/login",
            "/logout",
        )
    ):
        return await call_next(request)

    try:
        user = request.session.get("user")
        print(f"User: {user}")
        if not user:
            return RedirectResponse(url="/login")
    except Exception as e:
        print(f"Auth middleware check failed: {e}")
        return RedirectResponse(url="/login")

    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

oauth = OAuth()
oauth.register(
    name="auth0",
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    server_metadata_url=f'https://{os.getenv("AUTH0_DOMAIN")}/.well-known/openid-configuration',
    client_kwargs={
        "scope": "openid profile email",
        "redirect_uri": "http://localhost:8001/callback",
    },
)


async def check_auth0_session(request: Request) -> bool:
    try:
        user = request.session.get("user")
        return user is not None
    except Exception as e:
        print(f"check_auth0_session failed: {e}")
        return False


def greet(name):
    return f"Hello {name}!"


interface = gr.Interface(
    fn=greet, inputs="text", outputs="text", title="Protected Gradio App"
)


@app.get("/login")
async def login(request: Request):
    return await oauth.auth0.authorize_redirect(request, request.url_for("callback"))


@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        user = token.get("userinfo")
        if user:
            request.session["user"] = json.dumps(user)
            return RedirectResponse(url="/")
        return RedirectResponse(url="/login")
    except OAuthError as e:
        print(f"Callback error: {e}")
        return RedirectResponse(url="/login")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url=f"https://{os.getenv('AUTH0_DOMAIN')}/v2/logout?"
        f"client_id={os.getenv('AUTH0_CLIENT_ID')}&"
        f"returnTo=http://localhost:8001"
    )


app = gr.mount_gradio_app(app, interface, path="/")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8001)
