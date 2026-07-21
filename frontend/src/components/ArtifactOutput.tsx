import { useState } from 'react'

import { getArtifactDownload } from '../lib/api'
import type { ApiError, ArtifactReference, PortType } from '../lib/types'

interface ArtifactOutputProps {
  artifact: ArtifactReference
  kind: PortType
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ArtifactOutput({ artifact, kind }: ArtifactOutputProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const previewable = kind === 'image' || kind === 'audio' || kind === 'video'

  function loadSignedUrl(): void {
    setLoading(true)
    setError(null)
    getArtifactDownload(artifact.artifact_id)
      .then((download) => setUrl(download.url))
      .catch((caught: ApiError) => setError(caught.message))
      .finally(() => setLoading(false))
  }

  const label = artifact.filename ?? `Artifact #${artifact.artifact_id}`

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span>{label}</span>
        <span className="text-[var(--muted)]">
          {artifact.mime_type} · {formatBytes(artifact.size)}
        </span>
        {url ? (
          <a
            className="pixel-link underline"
            href={url}
            download={artifact.filename ?? undefined}
            target="_blank"
            rel="noreferrer"
          >
            Download
          </a>
        ) : (
          <button
            type="button"
            className="pixel-link underline"
            disabled={loading}
            onClick={loadSignedUrl}
          >
            {loading ? 'Preparing…' : previewable ? 'Preview' : 'Get download'}
          </button>
        )}
      </div>
      {error ? <div className="text-[var(--danger)]">{error}</div> : null}
      {url && kind === 'image' ? (
        <img
          className="max-h-64 max-w-full object-contain"
          src={url}
          alt={label}
          referrerPolicy="no-referrer"
        />
      ) : null}
      {url && kind === 'audio' ? (
        <audio className="max-w-full" controls preload="metadata" src={url} />
      ) : null}
      {url && kind === 'video' ? (
        <video className="max-h-64 max-w-full" controls preload="metadata" src={url} />
      ) : null}
    </div>
  )
}
