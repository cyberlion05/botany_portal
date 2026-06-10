"""WSGI entry-point (for PythonAnywhere / gunicorn)."""
from app import app as application
app = application
