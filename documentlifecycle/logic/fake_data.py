from __future__ import annotations
from typing import Any, List, Dict

def fake(value: Any = None, default: Any = None) -> Any:
    return value if value is not None else default

def fake_list() -> List[Dict[str, Any]]:
    return [
        {"id": 1, "title": "SOP 001 – Sample Intake", "status": "Draft",    "updated": "2025-09-25"},
        {"id": 2, "title": "WI 014 – Centrifuge Use", "status": "Review",   "updated": "2025-09-26"},
        {"id": 3, "title": "VA 002 – Release Rule",   "status": "Approved", "updated": "2025-09-27"},
    ]

def fake_detail(doc_id: int) -> Dict[str, Any]:
    status = "Draft" if doc_id == 1 else ("Review" if doc_id == 2 else "Approved")
    return {
        "id": doc_id, "title": f"Document #{doc_id}", "status": status,
        "updated": "2025-09-26", "author": "User A", "version": "1.3",
        "path": f"C:/docs/document_{doc_id:03d}.docx",
    }
