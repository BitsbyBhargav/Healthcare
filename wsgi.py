"""PythonAnywhere WSGI entry point. Configure environment before importing."""
from app import create_app

application = create_app()
