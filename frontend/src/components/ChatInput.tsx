import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { ArrowUp, Loader2, Paperclip } from 'lucide-react';
import { useDocuments } from '../contexts/DocumentsContext';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    placeholder?: string;
}

export function ChatInput({ onSend, disabled = false, placeholder = "Ask a question..." }: ChatInputProps) {
    const [input, setInput] = useState('');
    const { uploadFiles, uploads } = useDocuments();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const isUploading = Object.values(uploads).some(u => u.status === 'processing');

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto'; // Reset to calculate correct scrollHeight
            const newHeight = Math.min(textarea.scrollHeight, 200);
            textarea.style.height = `${newHeight}px`;
        }
    }, [input]);

    const handleSend = () => {
        const trimmed = input.trim();
        if (trimmed && !disabled) {
            onSend(trimmed);
            setInput('');
            // Reset height manually ensures cleaner transition
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
            if (file) {
                toast.error('Invalid file type', {
                    description: 'Only PDF files are supported',
                });
            }
            e.target.value = '';
            return;
        }

        uploadFiles([file]);
        e.target.value = '';
    };

    return (
        <div className={cn(
            "group/input flex w-full min-w-0 items-end gap-2 rounded-[20px] border border-border/80 bg-card/85 p-2 shadow-[0_22px_70px_-48px_rgba(15,23,42,0.55)] backdrop-blur-xl transition-[border-color,background,box-shadow,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] focus-within:border-primary/45 focus-within:bg-card focus-within:shadow-[0_26px_80px_-52px_hsl(var(--primary)/0.55)]",
            disabled && "opacity-50 pointer-events-none"
        )}>
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="hidden"
            />

            <Button
                variant="ghost"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isUploading}
                className="h-11 w-11 shrink-0 rounded-[15px] text-muted-foreground transition-all duration-200 hover:bg-muted/70 hover:text-foreground active:scale-[0.96]"
                title="Attach PDF"
            >
                {isUploading ? (
                    <Loader2 size={20} className="animate-spin" />
                ) : (
                    <Paperclip size={20} />
                )}
            </Button>

            <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                rows={1}
                className="min-h-11 max-h-[200px] min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-[10px] text-base leading-relaxed shadow-none placeholder:text-muted-foreground/60 focus-visible:ring-0 focus-visible:ring-offset-0"
                style={{ height: '44px' }}
            />

            <Button
                size="icon"
                onClick={handleSend}
                disabled={disabled || !input.trim()}
                className={cn(
                    "h-11 w-11 shrink-0 rounded-[15px] transition-all duration-200 active:scale-[0.94]",
                    !input.trim()
                        ? "bg-muted text-muted-foreground"
                        : "bg-primary text-primary-foreground shadow-[0_14px_36px_-24px_hsl(var(--primary)/0.8)] hover:bg-primary/90"
                )}
                aria-label="Send"
            >
                <ArrowUp size={20} />
            </Button>
        </div>
    );
}
