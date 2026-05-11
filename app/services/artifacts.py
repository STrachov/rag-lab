from pathlib import Path

from app.core.config import get_settings


class ArtifactService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or get_settings().data_dir

    def artifact_root(self) -> Path:
        return self.data_dir / "artifacts"
