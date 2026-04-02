import { Clock } from 'lucide-react';

export function TimesheetPage() {
  return (
    <div className="flex flex-col h-full bg-background">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
        <Clock className="w-5 h-5 text-primary" />
        <h1 className="font-display font-semibold text-foreground">Time Sheet</h1>
      </div>
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Time sheet module — coming soon.
      </div>
    </div>
  );
}
