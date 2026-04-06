import os
from pathlib import Path
import random
import string
import threading

import gradio as gr

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyQuery
from passlib.context import CryptContext
from sqlmodel import Session

from config.config import CURR_USER_FILE, RESULTS_FULL_PATH
from config.database import User, create_db_and_tables, engine, select
from utils.download_merge_crop import run_cleanup_pass, cleanup_old_jobs
from interface import interface
import schema

""" Read environment variables """

load_dotenv()
SCRIPT_NAME = os.getenv("SCRIPT_NAME", default="/")

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
              root_path=SCRIPT_NAME,
              lifespan=lifespan)

x_api_key = os.getenv("API_KEY", default = "Cr0p4ndM3rg3S3rv1c3")

query_scheme = APIKeyQuery(name="x_api_key")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password() -> str:
    length = random.randint(8, 32)
    characters = string.ascii_letters + string.digits
    password = "".join(random.choice(characters) for i in range(length))
    return password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> bool:
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
    if not user:
        return False
    if not verify_password(password, user.password):
       return False
    # TODO: Set the user name as a global variable for other files to read and use!
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

    username = "user-" + "".join(random.choices("0123456789", k=4))
    password = get_password()
    hashed_password = get_password_hash(password)
    db_user = User(username=username, password=hashed_password)

    with open(CURR_USER_FILE, "w") as f:
        f.write(username)

    with Session(engine) as session:
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    data = schema.copy()
    data["jsonforms:data"]["username"] = username
    data["jsonforms:data"]["password"] = password

    return data

app = gr.mount_gradio_app(app, interface, path="/", root_path=SCRIPT_NAME, auth=authenticate_user)

