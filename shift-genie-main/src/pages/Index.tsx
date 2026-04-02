import { AxisProvider } from '@/context/AxisContext';
import { ContextBar } from '@/components/ContextBar';
import { ChatPanel } from '@/components/ChatPanel';
import { ShiftCalendar } from '@/components/ShiftCalendar';

const Index = () => {
  return (
    <AxisProvider>
      <div className="flex flex-col h-screen overflow-hidden bg-background">
        <ContextBar />
        <div className="flex flex-1 min-h-0">
          <div className="w-[380px] flex-shrink-0">
            <ChatPanel />
          </div>
          <div className="flex-1 min-w-0">
            <ShiftCalendar />
          </div>
        </div>
      </div>
    </AxisProvider>
  );
};

export default Index;
