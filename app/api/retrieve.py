from fastapi import APIRouter, status

router = APIRouter()


@router.post("/retrieve", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def retrieve() -> dict[str, str]:
    return {"status": "not_implemented"}
