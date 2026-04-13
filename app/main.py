import os
import random
import string
import threading
import bcrypt
import structlog

import gradio as gr

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyQuery
from pathlib import Path
from sqlmodel import Session

from config.config import HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, RESULTS_FULL_PATH
from config.database import User, create_db_and_tables, engine, select
from pipelines.download_merge_crop_minio import run_cleanup_pass, cleanup_old_jobs
from interface import interface
from schema import schema

logger = structlog.get_logger()

""" Read environment variables """

load_dotenv()

# --- Lifespan handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    base_dir = Path(RESULTS_FULL_PATH)

    # Startup logic
    create_db_and_tables()
    run_cleanup_pass(base_dir=base_dir)
    start_cleanup(base_dir=base_dir)

    yield  #  App runs here

    # Shutdown logic (optional for now)
    # TODO: optional

app = FastAPI(title="Satellite Crop and Merge Downloader API",
              description="Agrotech application to download satellite data from specific geometry",
              lifespan=lifespan)

x_api_key = os.getenv("API_KEY", default = "Cr0p4ndM3rg3S3rv1c3")

query_scheme = APIKeyQuery(name="x_api_key")

def get_password() -> str:
    length = random.randint(8, 32)
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for i in range(length))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Checkpw compares the plain text bytes against the hashed bytes
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    # Use bcrypt directly to hash the plain text
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def authenticate_user(username: str, password: str) -> bool:
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
    if not user:
        return False
    if not verify_password(password, user.password):
       return False
    return True

def start_cleanup(base_dir=Path(RESULTS_FULL_PATH)):
    thread = threading.Thread(
        target=cleanup_old_jobs,
        args=(base_dir,),
        daemon=True
    )
    thread.start()


@app.get("/json", response_model=dict)
def new_user(api_key: str = Depends(query_scheme)) -> dict:
    if api_key != x_api_key:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    logger.info("New user authenticated, generating credentials and response data...")

    username = "user-" + "".join(random.choices("0123456789", k=4))
    password = get_password()
    hashed_password = get_password_hash(password)
    db_user = User(username=username, password=hashed_password)

    with Session(engine) as session:
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    data = schema.copy()
    data["jsonforms:data"]["username"] = username
    data["jsonforms:data"]["password"] = password

    logger.info("User credentials generated and stored in database successfully!")

    return data

app = gr.mount_gradio_app(
    app,
    interface,
    path="",
    auth=authenticate_user,
    theme="soft",
    head=JS_RECIEVER,
    css=HIDE_MAP_TEXTBOX_CSS
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)