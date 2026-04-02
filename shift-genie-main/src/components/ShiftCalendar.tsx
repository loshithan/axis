import { useMemo, useCallback, useState } from 'react';
import { Calendar, momentLocalizer, Views, Event } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { useQuery } from '@tanstack/react-query';
import { CalendarDays, Loader2 } from 'lucide-react';
import { Shift, ShiftRole } from '@/types/shift';
import { ShiftListItem, fetchShifts } from '@/lib/api';
import { useAxis } from '@/context/AxisContext';

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

const DEPT_TO_ROLE: Record<string, ShiftRole> = {
  icu: 'nurse',
  emergency: 'nurse',
  ward_general: 'nurse',
  ground_crew: 'tech',
  maritime_ops: 'tech',
  dispatch: 'admin',
};

function toRole(departmentCode: string): ShiftRole {
  return DEPT_TO_ROLE[departmentCode] ?? 'admin';
}

function combineDateTime(dateStr: string, timeStr: string): Date {
  // dateStr: "YYYY-MM-DD", timeStr: "HH:MM:SS"
  return new Date(`${dateStr}T${timeStr}`);
}

function fmtTime(timeStr: string): string {
  return timeStr.slice(0, 5); // "HH:MM:SS" → "HH:MM"
}

function itemToShift(item: ShiftListItem): Shift {
  const start = combineDateTime(item.date, item.start_time);
  const end = combineDateTime(item.date, item.end_time);
  if (end <= start) end.setDate(end.getDate() + 1); // overnight shift
  const timeRange = `${fmtTime(item.start_time)}–${fmtTime(item.end_time)}`;
  return {
    id: String(item.id),
    title: item.worker_name
      ? `${timeRange} — (${item.shift_type_name} — ${item.worker_name})`
      : `${timeRange} — (${item.shift_type_name})`,
    start,
    end,
    role: toRole(item.department_code),
    employee: item.worker_name || undefined,
  };
}

export function ShiftCalendar() {
  const [view, setView] = useState<(typeof Views)[keyof typeof Views]>(Views.MONTH);
  const [date, setDate] = useState(new Date());
  const { sbuCode, departmentCode } = useAxis();

  // Compute query date range from current calendar view
  const { rangeStart, rangeEnd } = useMemo(() => {
    const d = new Date(date);
    if (view === Views.WEEK) {
      const s = new Date(d);
      s.setDate(d.getDate() - d.getDay());
      const e = new Date(s);
      e.setDate(s.getDate() + 6);
      return { rangeStart: s, rangeEnd: e };
    }
    if (view === Views.DAY) {
      return { rangeStart: d, rangeEnd: d };
    }
    // Month view: fetch current month
    const s = new Date(d.getFullYear(), d.getMonth(), 1);
    const e = new Date(d.getFullYear(), d.getMonth() + 1, 0);
    return { rangeStart: s, rangeEnd: e };
  }, [date, view]);

  const startStr = rangeStart.toISOString().slice(0, 10);
  const endStr = rangeEnd.toISOString().slice(0, 10);

  const { data: items = [], isFetching } = useQuery({
    queryKey: ['shifts', sbuCode, departmentCode, startStr, endStr],
    queryFn: () => fetchShifts(sbuCode, departmentCode, startStr, endStr),
    enabled: !!sbuCode && !!departmentCode,
  });

  const shifts = useMemo(() => items.map(itemToShift), [items]);

  const events: Event[] = useMemo(() =>
    shifts.map(s => ({ title: s.title, start: s.start, end: s.end, resource: s })),
    [shifts],
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
          {isFetching && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {Object.entries(ROLE_COLORS).map(([role, color]) => (
            <div key={role} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
              <span className="capitalize">{role}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Calendar */}
      <div className="flex-1 p-4 overflow-hidden">
        {!sbuCode || !departmentCode ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Select an SBU and department to view the schedule.
          </div>
        ) : (
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
        )}
      </div>
    </div>
  );
}
