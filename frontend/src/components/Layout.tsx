import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { ScrollArea } from './ui/scroll-area';

interface LayoutProps {
    children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
    return (
        <div className="flex h-screen bg-[var(--color-bg)] text-[var(--color-text)] transition-colors duration-300 overflow-hidden">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
                <ScrollArea className="flex-1">
                    <main className="px-4 py-6">
                        <div className="max-w-5xl mx-auto w-full">
                            {children}
                        </div>
                    </main>
                </ScrollArea>
            </div>
        </div>
    );
}
