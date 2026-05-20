import os
import pymysql
from sqlmodel import Field, SQLModel, create_engine

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=100, unique=True)
    password: str = Field(max_length=100)

db_host = os.getenv("DB_HOST")
root_password = os.getenv("DB_ROOT_PASSWORD")

app_db_name = os.getenv("DB_NAME")
app_user = os.getenv("DB_USER")
app_password = os.getenv("DB_APP_PASSWORD")

mariadb_url = f"mysql+pymysql://{app_user}:{app_password}@{db_host}:3306/{app_db_name}"
engine = create_engine(mariadb_url, echo=True)

def provision_database_and_user():
    """Connects as root to create the database and a restricted user."""
    try:
        connection = pymysql.connect(
            host=db_host,
            user="root",
            password=root_password,
            autocommit=True
        )

        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{app_db_name}`;")
            cursor.execute(f"CREATE USER IF NOT EXISTS '{app_user}'@'%' IDENTIFIED BY '{app_password}';")
            
            cursor.execute(f"GRANT ALL PRIVILEGES ON `{app_db_name}`.* TO '{app_user}'@'%';")
            cursor.execute("FLUSH PRIVILEGES;")
            
        print(f"Provisioning complete for {app_db_name}.")
    except Exception as e:
        print(f"Error provisioning database: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

def start_database_connection():
    """Connects using the restricted app user to create tables and run the app."""
    try:
        SQLModel.metadata.create_all(engine)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Error initializing database tables: {e}")