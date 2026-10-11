"""Hugging Face Spaces entrypoint (Gradio SDK compatible)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend directory to sys.path so 'app' package is found
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Default environment for Hugging Face Spaces (port 7860, 0.0.0.0)
os.environ.setdefault("URBIS_HOST", "0.0.0.0")
os.environ.setdefault("URBIS_PORT", "7860")

import gradio as gr
import uvicorn
from app.main import app as fastapi_app

# Gradio interface embedding the platform
with gr.Blocks(title="ZoneScore — GeoSafe Analytics") as demo:
    gr.HTML(
        """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 10px;">
            <h2 style="margin: 0 0 6px 0; color: #1e293b;">🗺️ ZoneScore — GeoSafe Cross-Border Platform</h2>
            <p style="margin: 0 0 10px 0; color: #64748b; font-size: 14px;">
                Plateforme d'analyse et scoring géospatial H3 (Sécurité, Quiétude, Famille).
            </p>
            <iframe src="/" style="width: 100%; height: 90vh; border: 1px solid #cbd5e1; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08);"></iframe>
        </div>
        """
    )

# Mount Gradio app onto FastAPI app
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("URBIS_PORT", 7860)))
    host = os.environ.get("URBIS_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
