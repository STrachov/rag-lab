from fastapi import APIRouter, status

router = APIRouter()


@router.post("/ask", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def ask() -> dict[str, str]:
    return {"status": "not_implemented"}
