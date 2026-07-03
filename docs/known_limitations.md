# Known Limitations

## Oversized Non-Table OCR Blocks

Oversized markdown tables are split into row-bounded chunks and the full table is kept as a local artifact. Oversized non-table OCR blocks are currently preserved as a single chunk to avoid splitting sentences or extracted prose in a way that loses page and section context.

This means a very large body/caption block can still exceed the nominal chunk token target. A production hardening pass should add sentence- or paragraph-aware splitting for non-table segments while preserving page, section, and source metadata.

## OCR Provider Submission Uses Base64 Payloads

Uploads are streamed to local disk before ingestion and are capped by `MAX_UPLOAD_MB` (50 MB by default). The OCR provider submission step is still simpler: `parse_pdf_to_segments()` reads the whole PDF from disk, base64-encodes it, and sends it to Mistral OCR as a `data:application/pdf;base64,...` document URL.

That path is acceptable for local demos and interview-sized PDFs, but it is not a scalable large-document ingestion strategy. The upload size limit should stay conservative until OCR moves to a provider file-upload flow or object-store URL flow that avoids duplicating the full PDF in process memory and JSON request payloads.
