"""RAG (vector store) constants."""

# Cap on an uploaded document's raw size before text extraction, so a huge
# file can't be read fully into memory or blow up embedding time.
MAX_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024
