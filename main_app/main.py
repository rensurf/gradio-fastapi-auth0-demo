import json
import os
from pathlib import Path

from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

oauth = OAuth()
oauth.register(
    name="auth0",
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    server_metadata_url=f'https://{os.getenv("AUTH0_DOMAIN")}/.well-known/openid-configuration',
    client_kwargs={
        "scope": "openid profile email",
    },
)


async def get_current_user(request: Request):
    user = request.session.get("user")
    if user:
        return json.loads(user)
    return None


@app.get("/")
async def home(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": user, "gradio_url": os.getenv("GRADIO_APP_URL")},
    )


@app.get("/login")
async def login(request: Request):
    redirect_uri = f"{os.getenv('MAIN_APP_URL')}/callback"
    return await oauth.auth0.authorize_redirect(request, redirect_uri)


@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        user = token.get("userinfo")
        request.session["user"] = json.dumps(user)
        return RedirectResponse(url="/")
    except OAuthError as error:
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": error.error}
        )


@app.get("/logout")
async def logout(request: Request, response: Response):
    request.session.pop("user", None)
    return RedirectResponse(
        url=f"https://{os.getenv('AUTH0_DOMAIN')}/v2/logout?"
        f"client_id={os.getenv('AUTH0_CLIENT_ID')}&"
        f"returnTo={os.getenv('MAIN_APP_URL')}"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
