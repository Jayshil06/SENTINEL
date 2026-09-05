"""
Vercel Serverless Function Entrypoint for Project SENTINEL
Bridges incoming serverless requests to the FastAPI application.
"""
import os
import sys

# Add project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.main import app

# Vercel ASGI handler expects `app`
