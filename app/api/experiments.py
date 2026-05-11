from fastapi import APIRouter, status

router = APIRouter()


@router.post("/experiments", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_experiment() -> dict[str, str]:
    return {"status": "not_implemented"}
