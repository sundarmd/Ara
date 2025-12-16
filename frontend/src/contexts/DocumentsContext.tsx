import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { api } from '../services/api';
import { API_BASE_URL } from '../config/constants';
import { toast } from 'sonner';

export interface Document {
    doc_id: string;
    filename: string;
    bank: string;
    title: string;
    asset_class?: string;
    report_date?: string;
}

export interface FileProgress {
    filename: string;
    step: string;
    percent: number;
    detail: string;
    status: 'processing' | 'complete' | 'duplicate' | 'error';
    bank?: string;
    asset_class?: string;
}

interface DocumentsContextType {
    documents: Document[];
    refreshDocuments: () => Promise<void>;
    isLoading: boolean;
    error: string | null;
    uploads: Record<string, FileProgress>;
    uploadFiles: (files: File[]) => Promise<void>;
    deleteDocument: (docId: string) => Promise<void>;
}

const DocumentsContext = createContext<DocumentsContextType | undefined>(undefined);

export function DocumentsProvider({ children }: { children: ReactNode }) {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploads, setUploads] = useState<Record<string, FileProgress>>({});

    const refreshDocuments = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.listDocuments();
            setDocuments(data.documents || []);
        } catch (error) {
            console.error('Failed to fetch documents:', error);
            setError(error instanceof Error ? error.message : 'Failed to load documents');
        } finally {
            setIsLoading(false);
        }
    }, []);

    const uploadFiles = useCallback(async (files: File[]) => {
        if (files.length === 0) return;

        const initial: Record<string, FileProgress> = {};
        files.forEach(f => {
            initial[f.name] = {
                filename: f.name,
                step: 'start',
                percent: 0,
                detail: 'Starting...',
                status: 'processing',
            };
        });
        setUploads(initial);

        const formData = new FormData();
        files.forEach(file => formData.append('files', file));

        try {
            const response = await fetch(`${API_BASE_URL}/upload`, {
                method: 'POST',
                body: formData,
            });

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) return;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.step === 'done') {
                                setTimeout(() => setUploads({}), 4000);
                                refreshDocuments();
                                continue;
                            }

                            const filename = data.file;
                            if (!filename) continue;

                            setUploads(prev => ({
                                ...prev,
                                [filename]: {
                                    filename,
                                    step: data.step,
                                    percent: data.percent || 0,
                                    detail: data.detail || '',
                                    status: data.step === 'complete' ? 'complete' :
                                        data.step === 'duplicate' ? 'duplicate' :
                                            data.step === 'error' ? 'error' : 'processing',
                                    bank: data.bank,
                                    asset_class: data.asset_class,
                                }
                            }));
                        } catch {
                            // Skip invalid JSON
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Upload error:', error);
            setUploads(prev => {
                const updated = { ...prev };
                Object.keys(updated).forEach(k => {
                    if (updated[k].status === 'processing') {
                        updated[k] = { ...updated[k], status: 'error', detail: 'Network error', percent: 100 };
                    }
                });
                return updated;
            });
            setTimeout(() => setUploads({}), 4000);
        }
    }, [refreshDocuments]);

    const deleteDocument = useCallback(async (docId: string) => {
        const doc = documents.find(d => d.doc_id === docId);
        const filename = doc?.filename || 'Document';

        try {
            await api.deleteDocument(docId);
            setDocuments(prev => prev.filter(d => d.doc_id !== docId));
            toast.success(`${filename} deleted`);
        } catch (error) {
            console.error('Failed to delete document:', error);
            toast.error('Failed to delete document');
            throw error;
        }
    }, [documents]);

    // Initial fetch
    useEffect(() => {
        refreshDocuments();
    }, [refreshDocuments]);

    return (
        <DocumentsContext.Provider value={{ documents, refreshDocuments, isLoading, error, uploads, uploadFiles, deleteDocument }}>
            {children}
        </DocumentsContext.Provider>
    );
}

export function useDocuments() {
    const context = useContext(DocumentsContext);
    if (context === undefined) {
        throw new Error('useDocuments must be used within a DocumentsProvider');
    }
    return context;
}
