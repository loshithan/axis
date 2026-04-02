import { useState } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { ShiftCalendar } from '@/components/ShiftCalendar';
import { SwapPanel } from '@/components/SwapPanel';
import { CalendarDays, ArrowLeftRight } from 'lucide-react';

type RightTab = 'schedule' | 'swaps';

const Index = () => {
  const [rightTab, setRightTab] = useState<RightTab>('schedule');

  return (
    <div className="flex h-full">
      {/* Left: Chat */}
      <div className="w-[360px] flex-shrink-0 border-r border-border">
        <ChatPanel />
      </div>

      {/* Right: tabbed panel */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex border-b border-border px-5 bg-background flex-shrink-0">
          <button
            onClick={() => setRightTab('schedule')}
            className={`flex items-center gap-2 py-3 px-1 mr-6 text-sm font-medium border-b-2 transition-colors ${
              rightTab === 'schedule'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <CalendarDays className="w-4 h-4" />
            Schedule
          </button>
          <button
            onClick={() => setRightTab('swaps')}
            className={`flex items-center gap-2 py-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              rightTab === 'swaps'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <ArrowLeftRight className="w-4 h-4" />
            Swap Management
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-hidden">
          {rightTab === 'schedule' ? <ShiftCalendar /> : <SwapPanel />}
        </div>
      </div>
    </div>
  );
};

export default Index;
