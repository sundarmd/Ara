import { useState } from 'react';
import { X, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../services/api';
import { BANKS, ASSET_CLASSES } from '../config/constants';

interface UploadModalProps {
    file: File;
    onClose: () => void;
    onSuccess: () => void;
}

export function UploadModal({ file, onClose, onSuccess }: UploadModalProps) {
    const [bank, setBank] = useState('');
    const [assetClass, setAssetClass] = useState('');
    const [reportDate, setReportDate] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [result, setResult] = useState<{ status: string; message?: string } | null>(null);

    const handleUpload = async () => {
        if (!bank || !assetClass || !reportDate) return;

        setIsUploading(true);
        setResult(null);

        try {
            const response = await api.uploadReport(file, {
                bank,
                assetClass,
                reportDate
            });

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            // Parse SSE events
            let finalStatus = 'ok';
            let finalMessage = 'Report indexed successfully!';

            // Re-use logic for parsing generic SSE events roughly or just ignore progress details in Modal
            // But we need to check for errors/duplicates

            // Simple manual decoder loop similar to DropZone or api.parseSSEStream
            // We use api.parseSSEStream helper
            for await (const event of api.parseSSEStream<any>(reader)) {
                if (event.step === 'error') {
                    throw new Error(event.detail || 'Upload failed');
                }
                if (event.step === 'duplicate') {
                    finalStatus = 'duplicate';
                    finalMessage = `Already indexed (${event.bank || 'Unknown'})`;
                }
                if (event.step === 'done' || event.step === 'complete') {
                    // Success
                }
            }

            setResult({ status: finalStatus, message: finalMessage });

            if (finalStatus === 'ok') {
                setTimeout(() => {
                    onSuccess();
                    onClose();
                }, 1500);
            }
        } catch (error: any) {
            setResult({ status: 'error', message: error.message || 'Upload failed' });
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
            <div
                className="bg-[var(--color-surface)] rounded-xl p-6 w-full max-w-md shadow-2xl border border-[var(--color-border)]"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-[var(--color-text)]">Upload Research Report</h3>
                    <button onClick={onClose} className="p-1 hover:bg-[var(--color-bg)] rounded">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* File info */}
                <div className="flex items-center gap-3 p-3 rounded-lg bg-[var(--color-bg)] mb-4">
                    <FileText className="w-8 h-8 text-primary" />
                    <div className="flex-1 min-w-0">
                        <p className="font-medium text-[var(--color-text)] truncate">{file.name}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                    </div>
                </div>

                {/* Form */}
                <div className="space-y-3 mb-4">
                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Bank</label>
                        <select
                            value={bank}
                            onChange={(e) => setBank(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        >
                            <option value="">Select bank...</option>
                            {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Asset Class</label>
                        <select
                            value={assetClass}
                            onChange={(e) => setAssetClass(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        >
                            <option value="">Select asset class...</option>
                            {ASSET_CLASSES.map(a => <option key={a} value={a}>{a}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Report Date</label>
                        <input
                            type="date"
                            value={reportDate}
                            onChange={(e) => setReportDate(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        />
                    </div>
                </div>

                {/* Result message */}
                {result && (
                    <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-sm ${result.status === 'ok'
                        ? 'bg-green-500/10 text-green-400'
                        : result.status === 'duplicate'
                            ? 'bg-yellow-500/10 text-yellow-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}>
                        {result.status === 'ok' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                        {result.message}
                    </div>
                )}

                {/* Upload button */}
                <button
                    onClick={handleUpload}
                    disabled={!bank || !assetClass || !reportDate || isUploading}
                    className="w-full py-2.5 px-4 bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors active:scale-[0.98]"
                >
                    {isUploading ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Processing...
                        </>
                    ) : (
                        'Upload & Index'
                    )}
                </button>
            </div>
        </div>
    );
}
