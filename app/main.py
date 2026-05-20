import os
import io
import random
import string
import threading
import structlog
import zipfile
import requests
import uvicorn

import gradio as gr

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyQuery
from passlib.context import CryptContext
from pathlib import Path
from sqlmodel import Session, select

from utils.io_utils import run_cleanup_pass, cleanup_old_jobs
from config.config import ASSETS_DIR, HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, RESULTS_FULL_PATH, SCRIPT_NAME
from config.database import User, engine, provision_database_and_user, start_database_connection
from interface import interface
from schema import schema

logger = structlog.get_logger()

""" Read environment variables """

load_dotenv()
KML_FILENAME = "S2A_OPER_GIP_TILPAR_MPC__20151209T095117_V20150622T000000_21000101T000000_B00"
KML_FILE_URL = "https://sentiwiki.copernicus.eu/__attachments/1692737/{KML_FILENAME}.zip?inst-v=4ece9b51-c9c2-42f6-96f6-479e12c9d659"


# --- Lifespan handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    base_dir = Path(RESULTS_FULL_PATH)

    # Startup logic
    run_cleanup_pass(base_dir=base_dir)
    start_cleanup(base_dir=base_dir)

    # Fetch Sentinel2 Grid KML file
    try:
        if not os.path.exists(str(ASSETS_DIR / str(KML_FILENAME + ".kml"))):
            response = requests.get(KML_FILE_URL, stream=True)
            response.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(response.content))
            z.extractall(ASSETS_DIR)
            logger.info("Successfully downloaded and extracted KML files on startup.")
        else:
            logger.info("KML file detected and already available on startup.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
    except zipfile.BadZipFile:
        logger.error("The URL didn't actually return a valid ZIP file.")

    # Startup database
    provision_database_and_user()
    start_database_connection()

    yield  #  App runs here

app = FastAPI(title="Satellite Crop and Merge Downloader API",
              description="Agrotech application to download satellite data using specific geometry",
              root_path=SCRIPT_NAME,
              lifespan=lifespan,
              )

x_api_key = os.getenv("API_KEY", default="Cr0p4ndM3rg3S3rv1c3")
query_scheme = APIKeyQuery(name="x_api_key")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_session():
    """Yields a database session and safely closes it after the request finishes."""
    with Session(engine) as session:
        yield session

def get_password() -> str:
    length = random.randint(8, 32)
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))

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
    return verify_password(password, user.password)


def start_cleanup(base_dir=Path(RESULTS_FULL_PATH)):
    """Starts cleanup loop for old job dirs and results"""
    thread = threading.Thread(
        target=cleanup_old_jobs,
        args=(base_dir,),
        daemon=True
    )
    thread.start()


@app.get("/json", response_model=dict)
def new_user(
    request: Request, 
    api_key: str = Depends(query_scheme),
    session: Session = Depends(get_session)
) -> dict:
    if api_key != x_api_key:
        raise HTTPException(status_code=401, detail="Not authorized")

    username = "user-" + ''.join(random.choices('0123456789', k=4))
    password = get_password()
    hashed_password = get_password_hash(password)
    
    db_user = User(username=username, password=hashed_password)
    
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
        
    url = str(request.base_url)
    data = schema.copy()
    data["jsonforms:data"]["username"] = username
    data["jsonforms:data"]["password"] = password
    data["embed"] = url

    return data
print("SCRIPT_NAME", SCRIPT_NAME)
print("type", type(SCRIPT_NAME))
# SCRIPT_NAME = str(SCRIPT_NAME)
print("SCRIPT_NAME", SCRIPT_NAME)

app = gr.mount_gradio_app(
    app,
    interface,
    path="",
    root_path=SCRIPT_NAME,
    auth=authenticate_user,
    theme="gradio/monochrome",
    head=JS_RECIEVER,
    css=HIDE_MAP_TEXTBOX_CSS,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)