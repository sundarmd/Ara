import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { ScrollArea } from './ui/scroll-area';

interface LayoutProps {
    children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
    return (
        <div className="flex min-h-[100dvh] max-h-[100dvh] overflow-hidden bg-background text-foreground transition-colors duration-300">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                <ScrollArea className="min-w-0 flex-1">
                    <main className="overflow-hidden px-4 py-4 md:px-6 md:py-6">
                        <div className="mx-auto w-full max-w-6xl min-w-0">
                            {children}
                        </div>
                    </main>
                </ScrollArea>
            </div>
        </div>
    );
}
