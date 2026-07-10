"""Read background ingest job state from ARQ's own result store.

The Vector Collections upload endpoint enqueues ingestion onto the ARQ worker
and returns immediately; the frontend then polls this to learn when a document
has finished ingesting (or failed). We reuse ARQ's result store rather than
maintaining a separate job registry.
"""

from arq import ArqRedis
from arq.jobs import Job, JobStatus

from schemas import VectorJobStatusResponse


async def read_ingest_job_status(
    pool: ArqRedis, job_id: str
) -> VectorJobStatusResponse:
    """Map an ARQ ingest job's state to a client-facing status.

    Args:
        pool: The ARQ Redis pool.
        job_id: The job to inspect.

    Returns:
        ``processing`` while queued/running, ``ready`` once it has finished
        successfully (or its result has expired, which we treat as done), and
        ``failed`` with a detail message if the ingest raised.

    """
    job = Job(job_id, redis=pool)
    status = await job.status()

    # A result kept only ~1h by ARQ; once it expires the job reads as
    # not_found. By then the document is already in Qdrant, so treat it as done
    # rather than leaving a pending row spinning forever.
    if status in {JobStatus.not_found, JobStatus.deferred}:
        return VectorJobStatusResponse(status="ready")

    if status != JobStatus.complete:
        return VectorJobStatusResponse(status="processing")

    result_info = await job.result_info()
    if result_info is None:
        return VectorJobStatusResponse(status="ready")

    if result_info.success:
        result = result_info.result
        chunks = result.get("chunks_ingested") if isinstance(result, dict) else None
        return VectorJobStatusResponse(status="ready", chunks_ingested=chunks)

    return VectorJobStatusResponse(status="failed", detail=str(result_info.result))
