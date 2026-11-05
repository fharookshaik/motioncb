# API status and contract direction

## Current status

**Not implemented.** This document does not describe a running server. The repository has no
FastAPI app, route handlers, authentication, job store, or API integration tests. There is no API
startup command or endpoint to call.

## Intended first API surface

The first server should expose only validated study areas and artifacts that exist on disk:

| Method | Route | Intended behavior |
| --- | --- | --- |
| `GET` | `/health` | Process health and dependency readiness; do not report model readiness unless a valid checkpoint is loaded. |
| `GET` | `/v1/areas` | List areas represented by an imagery/model manifest; empty when none are supported. |
| `POST` | `/v1/jobs` | Validate a bounded area request and enqueue a durable, resumable inference job. |
| `GET` | `/v1/jobs/{job_id}` | Return persisted state, timestamps, progress, errors, and artifact links. |
| `GET` | `/v1/jobs/{job_id}/predictions` | Return georeferenced GeoJSON only after successful inference and validation. |

Job state should be persisted outside the API process with explicit transitions (`queued`,
`running`, `succeeded`, `failed`, `cancelled`). A job cannot be `succeeded` without a validated
georeferenced output, and restart recovery must resume or mark an interrupted job honestly. Test
split evaluation must remain a separate guarded command, never an interactive prediction endpoint.

## Data response rules

- Include CRS, model/config identifier, imagery interval, threshold, and provenance with results.
- Return unsupported areas as unsupported; do not substitute demo or fabricated predictions.
- Keep prediction GeoJSON small. Large vector/raster artifacts should be downloadable through
  explicit artifact URLs and GIS exports must retain coordinates and metadata.
- The API layer must delegate processing to `solarde`, not copy geospatial or model logic into
  route handlers.
