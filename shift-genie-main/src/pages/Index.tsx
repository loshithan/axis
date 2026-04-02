import { useState, useCallback } from 'react';
import { ChatPanel } from '@/components/ChatPanel';
import { ShiftCalendar } from '@/components/ShiftCalendar';
import { Shift } from '@/types/shift';

const Index = () => {
  const [shifts, setShifts] = useState<Shift[]>([]);

  const handleShiftsCreated = useCallback((newShifts: Shift[]) => {
    setShifts(prev => [...prev, ...newShifts]);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Chat Panel - Left Side */}
      <div className="w-[380px] flex-shrink-0">
        <ChatPanel onShiftsCreated={handleShiftsCreated} />
      </div>

      {/* Calendar - Right Side */}
      <div className="flex-1 min-w-0">
        <ShiftCalendar shifts={shifts} />
      </div>
    </div>
  );
};

export default Index;
