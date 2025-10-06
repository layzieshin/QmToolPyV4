"""
Tiny HTTP API to expose the same functionality to other processes/modules.

Run:
    uvicorn word_meta.logic.metadata_api:app --reload

GET /inspect?path=/full/path/to/file.docx
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pathlib import Path

from logic.metadata_extractor import get_document_metadata

app = FastAPI(title="Word Metadata API", version="1.0.0")


@app.get("/inspect")
def inspect(path: str = Query(..., description="Absolute path to a .docx file")):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        md = get_document_metadata(str(p))
        return md.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to inspect file: {ex}")