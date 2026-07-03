import { useState, ReactNode } from 'react';
import { Upload, FileText, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { useDocuments } from '../contexts/DocumentsContext';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';

interface DropZoneProps {
    children: ReactNode;
}

const STEP_LABELS: Record<string, string> = {
    ocr: 'Reading PDF',
    metadata: 'Detecting metadata',
    chunking: 'Building chunks',
    embedding: 'Generating embeddings',
    indexing: 'Indexing',
    recommendations: 'Finding recommendations',
    complete: 'Complete',
    duplicate: 'Already indexed',
    error: 'Error',
};

export function DropZone({ children }: DropZoneProps) {
    const [dragCounter, setDragCounter] = useState(0);
    const { uploads, uploadFiles } = useDocuments();

    const isDragging = dragCounter > 0;

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragCounter((prev) => prev + 1);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragCounter((prev) => Math.max(0, prev - 1));
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragCounter(0);

        const droppedFiles = Array.from(e.dataTransfer.files);
        const pdfFiles = droppedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));

        if (pdfFiles.length === 0) {
            toast.error('Invalid file type', {
                description: 'Only PDF files are supported'
            });
            return;
        }

        uploadFiles(pdfFiles);
    };

    const uploadList = Object.values(uploads);
    const hasUploads = uploadList.length > 0;

    return (
        <div
            className="relative min-h-[100dvh]"
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
        >
            {children}

            {/* Full-page overlay when dragging */}
            {isDragging && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/10 backdrop-blur-sm pointer-events-none">
                    <div className="rounded-[28px] border-2 border-dashed border-primary/60 bg-[var(--color-surface)] p-10 text-center shadow-[0_28px_90px_-58px_rgba(15,23,42,0.8)]">
                        <Upload className="mx-auto mb-3 h-12 w-12 text-primary" />
                        <h2 className="text-lg font-semibold text-[var(--color-text)]">
                            Drop to upload
                        </h2>
                    </div>
                </div>
            )}

            {/* Progress panel */}
            {hasUploads && (
                <div className="fixed bottom-6 right-6 z-50 w-80">
                    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl overflow-hidden">
                        {uploadList.map((file) => (
                            <div key={file.filename} className="p-4 border-b border-[var(--color-border)] last:border-b-0">
                                {/* Header with icon and filename */}
                                <div className="flex items-center gap-2 mb-2">
                                    {file.status === 'processing' && (
                                        <FileText className="w-4 h-4 text-primary flex-shrink-0" />
                                    )}
                                    {file.status === 'complete' && (
                                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                                    )}
                                    {file.status === 'duplicate' && (
                                        <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                                    )}
                                    {file.status === 'error' && (
                                        <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                                    )}
                                    <span className="text-sm font-medium text-[var(--color-text)] truncate flex-1">
                                        {file.filename}
                                    </span>
                                    {file.status === 'processing' && (
                                        <span className="text-xs font-mono text-primary">
                                            {file.percent}%
                                        </span>
                                    )}
                                </div>

                                {/* Progress bar */}
                                {file.status === 'processing' && (
                                    <div className="mb-2">
                                        <Progress value={file.percent} className="h-1" />
                                    </div>
                                )}

                                {/* Current step */}
                                <div className="text-xs text-[var(--color-text-muted)]">
                                    {STEP_LABELS[file.step] || file.step}: {file.detail}
                                </div>

                                {/* Result badges */}
                                {(file.status === 'complete' || file.status === 'duplicate') && file.bank && (
                                    <div className="mt-2 flex gap-2">
                                        <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary font-medium">
                                            {file.bank}
                                        </span>
                                        <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-border)] text-[var(--color-text-muted)]">
                                            {file.asset_class}
                                        </span>
                                    </div>
                                )}
                                {file.warnings && file.warnings.length > 0 && (
                                    <div className="mt-2 flex items-start gap-1 text-xs text-amber-600">
                                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                                        <span>{file.warnings.join(' ')}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
