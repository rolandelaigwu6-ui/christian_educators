"""Vercel entrypoint for the existing backend; public files use Vercel's CDN."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'back_end'))
from back_end import app  # noqa: E402, F401

# Declare the generated frontend explicitly so Vercel promotes it to the CDN.
# The build command creates this directory before Vercel's static discovery.
app.frontend('/', directory=Path(__file__).resolve().parent / 'public',
             fallback='404.html', check_dir=False)
