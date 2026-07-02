# Known Limitations

## Oversized Non-Table OCR Blocks

Oversized markdown tables are split into row-bounded chunks and the full table is kept as a local artifact. Oversized non-table OCR blocks are currently preserved as a single chunk to avoid splitting sentences or extracted prose in a way that loses page and section context.

This means a very large body/caption block can still exceed the nominal chunk token target. A production hardening pass should add sentence- or paragraph-aware splitting for non-table segments while preserving page, section, and source metadata.
