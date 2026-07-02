import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, X, Loader2 } from 'lucide-react';
import { API_BASE_URL, BANKS, ASSET_CLASSES } from '../config/constants';

interface UploadResult {
    status: 'ok' | 'already_indexed' | 'error';
    doc_id?: string;
    message?: string;
    existing?: {
        bank: string;
        asset_class: string;
        filename: string;
    };
}

export function FileUpload() {
    const [isDragging, setIsDragging] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [bank, setBank] = useState('');
    const [assetClass, setAssetClass] = useState('');
    const [reportDate, setReportDate] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile?.type === 'application/pdf') {
            setFile(droppedFile);
            setResult(null);
        }
    }, []);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) {
            setFile(selectedFile);
            setResult(null);
        }
    };

    const handleUpload = async () => {
        if (!file || !bank || !assetClass || !reportDate) return;

        setIsUploading(true);
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('bank', bank);
        formData.append('asset_class', assetClass);
        formData.append('report_date', reportDate);

        try {
            const response = await fetch(`${API_BASE_URL}/upload_report`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                setResult({ status: 'error', message: data.detail || 'Upload failed' });
            } else {
                setResult(data);
                if (data.status === 'ok') {
                    // Clear form on success
                    setFile(null);
                    setBank('');
                    setAssetClass('');
                    setReportDate('');
                }
            }
        } catch (error) {
            setResult({ status: 'error', message: 'Network error. Please try again.' });
        } finally {
            setIsUploading(false);
        }
    };

    const clearFile = () => {
        setFile(null);
        setResult(null);
    };

    return (
        <div className="bg-[var(--color-surface)] rounded-xl p-6 border border-[var(--color-border)]">
            <h3 className="text-lg font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Upload Research Report
            </h3>

            {/* Drop zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragging
                        ? 'border-primary bg-primary/10'
                        : 'border-[var(--color-border)] hover:border-primary/50'
                    }
          ${file ? 'bg-[var(--color-bg)]' : ''}
        `}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    onChange={handleFileSelect}
                    className="hidden"
                />

                {file ? (
                    <div className="flex items-center justify-center gap-3">
                        <FileText className="w-8 h-8 text-primary" />
                        <div className="text-left">
                            <p className="font-medium text-[var(--color-text)]">{file.name}</p>
                            <p className="text-xs text-[var(--color-text-muted)]">
                                {(file.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                        </div>
                        <button
                            onClick={(e) => { e.stopPropagation(); clearFile(); }}
                            className="p-1 hover:bg-[var(--color-bg)] rounded"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                ) : (
                    <>
                        <Upload className="w-10 h-10 mx-auto mb-2 text-[var(--color-text-muted)]" />
                        <p className="text-[var(--color-text)]">Drop PDF here or click to select</p>
                        <p className="text-xs text-[var(--color-text-muted)] mt-1">Only PDF files supported</p>
                    </>
                )}
            </div>

            {/* Form fields */}
            {file && (
                <div className="mt-4 grid grid-cols-3 gap-4">
                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                            Bank
                        </label>
                        <select
                            value={bank}
                            onChange={(e) => setBank(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        >
                            <option value="">Select...</option>
                            {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                            Asset Class
                        </label>
                        <select
                            value={assetClass}
                            onChange={(e) => setAssetClass(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        >
                            <option value="">Select...</option>
                            {ASSET_CLASSES.map(a => <option key={a} value={a}>{a}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                            Report Date
                        </label>
                        <input
                            type="date"
                            value={reportDate}
                            onChange={(e) => setReportDate(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm"
                        />
                    </div>
                </div>
            )}

            {/* Upload button */}
            {file && (
                <button
                    onClick={handleUpload}
                    disabled={!bank || !assetClass || !reportDate || isUploading}
                    className="mt-4 w-full py-2 px-4 bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors active:scale-[0.98]"
                >
                    {isUploading ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Processing...
                        </>
                    ) : (
                        <>
                            <Upload className="w-4 h-4" />
                            Upload & Index
                        </>
                    )}
                </button>
            )}

            {/* Result message */}
            {result && (
                <div className={`mt-4 p-3 rounded-lg flex items-start gap-2 ${result.status === 'ok'
                        ? 'bg-green-500/10 text-green-400'
                        : result.status === 'already_indexed'
                            ? 'bg-yellow-500/10 text-yellow-400'
                            : 'bg-red-500/10 text-red-400'
                    }`}>
                    {result.status === 'ok' ? (
                        <CheckCircle className="w-5 h-5 flex-shrink-0" />
                    ) : result.status === 'already_indexed' ? (
                        <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    ) : (
                        <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    )}
                    <div>
                        {result.status === 'ok' && (
                            <p className="font-medium">Report indexed successfully!</p>
                        )}
                        {result.status === 'already_indexed' && (
                            <>
                                <p className="font-medium">Duplicate file detected</p>
                                <p className="text-xs mt-1">
                                    Already indexed as {result.existing?.bank} - {result.existing?.filename}
                                </p>
                            </>
                        )}
                        {result.status === 'error' && (
                            <p className="font-medium">{result.message}</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
