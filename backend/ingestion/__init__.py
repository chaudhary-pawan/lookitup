"""ingestion package — lazy imports to avoid pulling in Celery/insightface at collection time."""

# Expose batch_processor directly — no heavy deps needed
from backend.ingestion.batch_processor import extract_images_from_zip


def __getattr__(name: str):
    """Lazy-load heavy submodules only when explicitly accessed."""
    if name == "process_album_task":
        from backend.ingestion.tasks import process_album_task  # noqa: PLC0415
        return process_album_task
    if name == "IngestionPipeline":
        from backend.ingestion.pipeline import IngestionPipeline  # noqa: PLC0415
        return IngestionPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["process_album_task", "IngestionPipeline", "extract_images_from_zip"]

