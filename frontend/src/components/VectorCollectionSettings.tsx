import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { uploadVectorDocument } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { ApiError } from '../lib/types'
import { useVectorCollections } from '../hooks/useVectorCollections'
import { useVectorDocuments } from '../hooks/useVectorDocuments'
import { useVectorUploadJobs } from '../hooks/useVectorUploadJobs'
import { VectorCollectionInput } from './VectorCollectionInput'

interface VectorCollectionSettingsProps {
  onError: (err: ApiError) => void
}

function VectorDocumentList({
  collection,
  onError,
}: {
  collection: string
  onError: (err: ApiError) => void
}) {
  const [confirmDeleteSource, setConfirmDeleteSource] = useState<string | null>(null)
  const { documents, loading, removeDocument } = useVectorDocuments({
    collection,
    onError,
  })

  async function handleDelete(source: string): Promise<void> {
    await removeDocument(source)
    setConfirmDeleteSource(null)
  }

  if (loading) {
    return <div className="text-xs text-[var(--muted)]">Loading documents...</div>
  }

  if (documents.length === 0) {
    return <div className="text-xs text-[var(--muted)]">No documents yet.</div>
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map((doc) => (
        <div key={doc.source} className="pixel-card">
          <div className="flex-1">
            <div className="text-sm">{doc.source}</div>
            <div className="text-xs text-[var(--muted)]">
              {doc.chunk_count} chunk{doc.chunk_count === 1 ? '' : 's'}
              {' · '}
              {doc.source_type}
              {doc.revision ? ` · rev ${doc.revision}` : ''}
            </div>
            <div className="text-xs text-[var(--muted)]">
              {doc.acl.visibility}
              {doc.expires_at
                ? ` · expires ${new Date(doc.expires_at).toLocaleString()}`
                : ' · retained'}
            </div>
          </div>
          {confirmDeleteSource === doc.source ? (
            <>
              <button
                type="button"
                className="pixel-icon danger"
                title="Confirm delete"
                onClick={() => void handleDelete(doc.source)}
              >
                ✓
              </button>
              <button
                type="button"
                className="pixel-icon"
                title="Cancel"
                onClick={() => setConfirmDeleteSource(null)}
              >
                ✕
              </button>
            </>
          ) : (
            <button
              type="button"
              className="pixel-icon danger"
              onClick={() => setConfirmDeleteSource(doc.source)}
            >
              Del
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

export function VectorCollectionSettings({ onError }: VectorCollectionSettingsProps) {
  const queryClient = useQueryClient()
  const [expandedCollection, setExpandedCollection] = useState<string | null>(null)
  const [confirmDeleteName, setConfirmDeleteName] = useState<string | null>(null)
  const [uploadCollection, setUploadCollection] = useState('')
  const [uploadSource, setUploadSource] = useState('')
  const [uploadSourceType, setUploadSourceType] = useState('upload')
  const [uploadExternalId, setUploadExternalId] = useState('')
  const [uploadRevision, setUploadRevision] = useState('')
  const [uploadRetentionDays, setUploadRetentionDays] = useState(0)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const {
    collections,
    loading: collectionsLoading,
    removeCollection,
    refreshCollections,
  } = useVectorCollections({
    onError,
  })

  const { pending, track: trackUpload } = useVectorUploadJobs({
    onReady: (upload) => {
      void refreshCollections()
      void queryClient.invalidateQueries({
        queryKey: queryKeys.vectorDocuments(upload.collection),
      })
    },
    onError,
  })

  function toggleExpanded(name: string): void {
    setExpandedCollection((current) => (current === name ? null : name))
  }

  async function handleDeleteCollection(name: string): Promise<void> {
    await removeCollection(name)
    if (expandedCollection === name) {
      setExpandedCollection(null)
    }
    setConfirmDeleteName(null)
  }

  async function handleUpload(): Promise<void> {
    if (!uploadFile || !uploadCollection.trim()) {
      return
    }
    const collection = uploadCollection.trim()
    setSubmitting(true)
    try {
      const job = await uploadVectorDocument(
        collection,
        uploadFile,
        uploadSource.trim() || undefined,
        {
          source_type: uploadSourceType.trim() || 'upload',
          external_id: uploadExternalId.trim() || undefined,
          revision: uploadRevision.trim() || undefined,
          retention_days:
            uploadRetentionDays > 0 ? uploadRetentionDays : undefined,
        },
      )
      // Ingestion continues on the worker; track the job and clear the form so
      // the user can queue the next file without waiting.
      trackUpload({ jobId: job.job_id, source: job.source, collection })
      setUploadFile(null)
      setUploadSource('')
      setUploadExternalId('')
      setUploadRevision('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error) {
      onError(error as ApiError)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {collectionsLoading ? (
          <div className="text-xs text-[var(--muted)]">Loading collections...</div>
        ) : collections.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No collections yet.</div>
        ) : null}
        {collections.map((collection) => (
          <div key={collection.name} className="flex flex-col gap-2">
            <div className="pixel-card">
              <button
                type="button"
                className="flex-1 text-left"
                onClick={() => toggleExpanded(collection.name)}
              >
                <div className="text-sm">{collection.name}</div>
                <div className="text-xs text-[var(--muted)]">
                  {collection.point_count} chunk
                  {collection.point_count === 1 ? '' : 's'}
                </div>
              </button>
              {confirmDeleteName === collection.name ? (
                <>
                  <button
                    type="button"
                    className="pixel-icon danger"
                    title="Confirm delete"
                    onClick={() => void handleDeleteCollection(collection.name)}
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    className="pixel-icon"
                    title="Cancel"
                    onClick={() => setConfirmDeleteName(null)}
                  >
                    ✕
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="pixel-icon danger"
                  onClick={() => setConfirmDeleteName(collection.name)}
                >
                  Del
                </button>
              )}
            </div>
            {expandedCollection === collection.name ? (
              <div className="ml-4 border-l border-white/10 pl-4">
                <VectorDocumentList
                  key={collection.name}
                  collection={collection.name}
                  onError={onError}
                />
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Upload document
        </div>
        <div className="flex flex-col gap-3">
          <label className="pixel-label">
            Collection
            <VectorCollectionInput
              collections={collections}
              value={uploadCollection}
              onChange={setUploadCollection}
              placeholder="my-documents"
            />
          </label>
          <label className="pixel-label">
            File
            <input
              ref={fileInputRef}
              className="pixel-input"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="pixel-label">
            Source (optional)
            <input
              className="pixel-input"
              value={uploadSource}
              onChange={(e) => setUploadSource(e.target.value)}
              placeholder="Defaults to the file name"
            />
          </label>
          <label className="pixel-label">
            Source type
            <input
              className="pixel-input"
              value={uploadSourceType}
              onChange={(e) => setUploadSourceType(e.target.value.toLowerCase())}
              placeholder="upload, drive, notion, confluence"
            />
          </label>
          <label className="pixel-label">
            External ID (optional)
            <input
              className="pixel-input"
              value={uploadExternalId}
              onChange={(e) => setUploadExternalId(e.target.value)}
              placeholder="Provider object ID"
            />
          </label>
          <label className="pixel-label">
            Revision / ETag (optional)
            <input
              className="pixel-input"
              value={uploadRevision}
              onChange={(e) => setUploadRevision(e.target.value)}
              placeholder="Unchanged revisions skip embedding"
            />
          </label>
          <label className="pixel-label">
            Retention days
            <input
              className="pixel-input"
              type="number"
              min={0}
              max={36500}
              value={uploadRetentionDays}
              onChange={(e) => setUploadRetentionDays(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            className="pixel-button small"
            disabled={submitting || !uploadFile || !uploadCollection.trim()}
            onClick={() => void handleUpload()}
          >
            {submitting ? 'Queuing...' : 'Upload'}
          </button>

          {pending.length > 0 ? (
            <div className="flex flex-col gap-2">
              {pending.map((item) => (
                <div key={item.jobId} className="pixel-card">
                  <div className="flex-1">
                    <div className="text-sm">{item.source}</div>
                    <div className="text-xs text-[var(--muted)]">
                      {item.collection}
                    </div>
                  </div>
                  <span className="pixel-processing">processing…</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
