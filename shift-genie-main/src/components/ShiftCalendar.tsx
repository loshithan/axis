import { useMemo, useCallback, useState } from 'react';
import { Calendar, momentLocalizer, Views, Event, SlotInfo } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, Loader2, Plus } from 'lucide-react';
import { Shift, ShiftRole } from '@/types/shift';
import { ShiftListItem, fetchShifts } from '@/lib/api';
import { useAxis } from '@/context/AxisContext';
import { ShiftModal } from './ShiftModal';

const localizer = momentLocalizer(moment);

const ROLE_COLORS: Record<ShiftRole, string> = {
  nurse: 'hsl(285, 55%, 38%)',
  doctor: 'hsl(210, 72%, 38%)',
  tech: 'hsl(32, 90%, 35%)',
  admin: 'hsl(340, 72%, 40%)',
};

const ROLE_BG: Record<ShiftRole, string> = {
  nurse: 'hsla(285, 55%, 45%, 0.12)',
  doctor: 'hsla(210, 72%, 45%, 0.12)',
  tech: 'hsla(32, 90%, 45%, 0.12)',
  admin: 'hsla(340, 72%, 45%, 0.12)',
};

const WORKER_TYPE_TO_ROLE: Record<string, ShiftRole> = {
  nurse: 'nurse',
  doctor: 'doctor',
  technician: 'tech',
  admin: 'admin',
};

function toRole(workerType: string): ShiftRole {
  return WORKER_TYPE_TO_ROLE[workerType] ?? 'admin';
}

function combineDateTime(dateStr: string, timeStr: string): Date {
  // dateStr: "YYYY-MM-DD", timeStr: "HH:MM:SS"
  return new Date(`${dateStr}T${timeStr}`);
}

function fmtTime(timeStr: string): string {
  return timeStr.slice(0, 5); // "HH:MM:SS" → "HH:MM"
}

function itemToShift(item: ShiftListItem): Shift & { _raw: ShiftListItem } {
  const start = combineDateTime(item.date, item.start_time);
  const end = combineDateTime(item.date, item.end_time);
  if (end <= start) end.setDate(end.getDate() + 1); // overnight shift
  const timeRange = `${fmtTime(item.start_time)}–${fmtTime(item.end_time)}`;
  const isOpen = item.status === 'open' || !item.worker_name;
  return {
    id: String(item.id),
    title: isOpen
      ? `${timeRange} — (${item.shift_type_name} — OPEN)`
      : `${timeRange} — (${item.shift_type_name} — ${item.worker_name})`,
    start,
    end,
    role: toRole(item.worker_type),
    employee: item.worker_name || undefined,
    _raw: item,
  };
}

export function ShiftCalendar() {
  const [view, setView] = useState<(typeof Views)[keyof typeof Views]>(Views.MONTH);
  const [date, setDate] = useState(new Date());
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();

  // Modal state
  const [modalMode, setModalMode] = useState<'create' | 'edit' | null>(null);
  const [modalDate, setModalDate] = useState<string | undefined>();
  const [modalShift, setModalShift] = useState<ShiftListItem | undefined>();

  function openCreate(slotDate: string) {
    setModalDate(slotDate);
    setModalShift(undefined);
    setModalMode('create');
  }

  function openEdit(shift: ShiftListItem) {
    setModalShift(shift);
    setModalDate(undefined);
    setModalMode('edit');
  }

  function closeModal() {
    setModalMode(null);
  }

  function onSaved() {
    queryClient.invalidateQueries({ queryKey: ['shifts'] });
  }

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
    shifts.map(s => ({ title: s.title, start: s.start, end: s.end, resource: s as Shift & { _raw: ShiftListItem } })),
    [shifts],
  );

  const eventStyleGetter = useCallback((event: Event) => {
    const shift = event.resource as Shift & { _raw: ShiftListItem };
    const status = shift._raw?.status;

    // PENDING: assigned worker has a leave request — flag as uncovered/awaiting swap
    if (status === 'pending') {
      return {
        style: {
          backgroundColor: 'hsla(38, 92%, 50%, 0.15)',
          color: 'hsl(38, 92%, 40%)',
          borderLeft: '3px dashed hsl(38, 92%, 50%)',
          fontWeight: 600,
          opacity: 0.95,
        },
      };
    }

    // OPEN: no worker assigned
    const isOpen = !shift.employee || status === 'open';
    if (isOpen) {
      return {
        style: {
          backgroundColor: 'hsla(0, 0%, 50%, 0.12)',
          color: 'hsl(0, 0%, 60%)',
          borderLeft: '3px dashed hsl(0, 0%, 45%)',
          fontWeight: 500,
          opacity: 0.85,
        },
      };
    }

    return {
      style: {
        backgroundColor: ROLE_BG[shift.role],
        color: ROLE_COLORS[shift.role],
        borderLeft: `3px solid ${ROLE_COLORS[shift.role]}`,
        fontWeight: 500,
      },
    };
  }, []);

  const handleSelectSlot = useCallback((slot: SlotInfo) => {
    if (!sbuCode || !departmentCode) return;
    const d = slot.start instanceof Date ? slot.start.toISOString().slice(0, 10) : String(slot.start).slice(0, 10);
    openCreate(d);
  }, [sbuCode, departmentCode]);

  const handleSelectEvent = useCallback((event: Event) => {
    const shift = (event.resource as Shift & { _raw: ShiftListItem })._raw;
    if (shift) openEdit(shift);
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
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full border-2 border-dashed border-amber-500" style={{ backgroundColor: 'hsla(38,92%,50%,0.15)' }} />
              <span>pending swap</span>
            </div>
            {(Object.entries(ROLE_COLORS) as [ShiftRole, string][]).map(([role, color]) => (
              <div key={role} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="capitalize">{role === 'tech' ? 'technician' : role}</span>
              </div>
            ))}
          </div>
          {sbuCode && departmentCode && (
            <button
              onClick={() => openCreate(new Date().toISOString().slice(0, 10))}
              className="flex items-center gap-1.5 text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Shift
            </button>
          )}
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
            selectable
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            popup
            style={{ height: '100%' }}
          />
        )}
      </div>

      {/* Shift Modal */}
      {modalMode && (
        <ShiftModal
          mode={modalMode}
          initialDate={modalDate}
          shift={modalShift}
          onClose={closeModal}
          onSaved={onSaved}
        />
      )}
    </div>
  );
}
