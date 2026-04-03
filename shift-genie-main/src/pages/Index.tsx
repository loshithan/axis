import { useState } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { ShiftCalendar } from '@/components/ShiftCalendar';
import { SwapPanel } from '@/components/SwapPanel';
import { CalendarDays, ArrowLeftRight, MessageSquare, PanelLeftClose, PanelLeftOpen } from 'lucide-react';

type RightTab = 'schedule' | 'swaps';

const Index = () => {
  const [rightTab, setRightTab] = useState<RightTab>('schedule');
  const [chatOpen, setChatOpen] = useState(true);

  return (
    <div className="flex h-full">
      {/* Left: Chat (collapsible) */}
      <div className={`flex-shrink-0 border-r border-border transition-all duration-300 overflow-hidden ${chatOpen ? 'w-[360px]' : 'w-0'}`}>
        <div className="w-[360px] h-full">
          <ChatPanel />
        </div>
      </div>

      {/* Right: tabbed panel */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center border-b border-border px-5 bg-background flex-shrink-0">
          {/* Toggle button */}
          <button
            onClick={() => setChatOpen(o => !o)}
            className="flex items-center justify-center w-7 h-7 mr-3 rounded hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
            title={chatOpen ? 'Hide chat' : 'Show chat'}
          >
            {chatOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
          </button>

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

          {/* Chat indicator when hidden */}
          {!chatOpen && (
            <button
              onClick={() => setChatOpen(true)}
              className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Chat
            </button>
          )}
        </div>

        <div className="flex-1 min-h-0 overflow-hidden">
          {rightTab === 'schedule' ? <ShiftCalendar /> : <SwapPanel />}
        </div>
      </div>
    </div>
  );
};

export default Index;
