import { useMemo, useCallback, useState } from 'react';
import { Calendar, momentLocalizer, Views, Event } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { Shift, ShiftRole } from '@/types/shift';
import { CalendarDays } from 'lucide-react';

const localizer = momentLocalizer(moment);

const ROLE_COLORS: Record<ShiftRole, string> = {
  nurse: 'hsl(174, 72%, 46%)',
  doctor: 'hsl(262, 72%, 55%)',
  tech: 'hsl(32, 90%, 55%)',
  admin: 'hsl(340, 72%, 55%)',
};

const ROLE_BG: Record<ShiftRole, string> = {
  nurse: 'hsla(174, 72%, 46%, 0.18)',
  doctor: 'hsla(262, 72%, 55%, 0.18)',
  tech: 'hsla(32, 90%, 55%, 0.18)',
  admin: 'hsla(340, 72%, 55%, 0.18)',
};

interface ShiftCalendarProps {
  shifts: Shift[];
}

export function ShiftCalendar({ shifts }: ShiftCalendarProps) {
  const [view, setView] = useState<(typeof Views)[keyof typeof Views]>(Views.MONTH);
  const [date, setDate] = useState(new Date());

  const events: Event[] = useMemo(() =>
    shifts.map(s => ({
      title: s.title,
      start: s.start,
      end: s.end,
      resource: s,
    })),
    [shifts]
  );

  const eventStyleGetter = useCallback((event: Event) => {
    const shift = event.resource as Shift;
    return {
      style: {
        backgroundColor: ROLE_BG[shift.role],
        color: ROLE_COLORS[shift.role],
        borderLeft: `3px solid ${ROLE_COLORS[shift.role]}`,
        fontWeight: 500,
      },
    };
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-primary" />
          <h2 className="font-display font-semibold text-foreground">Schedule</h2>
        </div>
        <div className="flex items-center gap-3">
          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {Object.entries(ROLE_COLORS).map(([role, color]) => (
              <div key={role} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="capitalize">{role}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Calendar */}
      <div className="flex-1 p-4 overflow-hidden">
        <Calendar
          localizer={localizer}
          events={events}
          view={view}
          date={date}
          onView={(v) => setView(v)}
          onNavigate={(d) => setDate(d)}
          eventPropGetter={eventStyleGetter}
          views={[Views.MONTH, Views.WEEK, Views.DAY]}
          popup
          style={{ height: '100%' }}
        />
      </div>
    </div>
  );
}
