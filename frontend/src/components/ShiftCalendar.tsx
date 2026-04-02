"use client";

import { useMemo, useState } from "react";
import { Calendar, dateFnsLocalizer, Views } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { enUS } from "date-fns/locale/en-US";
import "react-big-calendar/lib/css/react-big-calendar.css";
import type { ShiftRow } from "@/lib/api";

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { weekStartsOn: 1 }),
  getDay,
  locales: { "en-US": enUS },
});

const STATUS_COLORS: Record<string, string> = {
  assigned:   "#3d8bfd",
  confirmed:  "#34d399",
  open:       "#fbbf24",
  unassigned: "#fbbf24",
  escalated:  "#f87171",
};

interface CalEvent {
  id: number;
  title: string;
  start: Date;
  end: Date;
  resource: ShiftRow;
}

export function ShiftCalendar({
  shifts,
  initialDate,
}: {
  shifts: ShiftRow[];
  initialDate?: Date;
}) {
  const [view, setView]   = useState<(typeof Views)[keyof typeof Views]>(Views.WEEK);
  const [date, setDate]   = useState<Date>(initialDate ?? new Date());

  const events = useMemo<CalEvent[]>(
    () =>
      shifts.map((s) => {
        const start = new Date(`${s.date}T${s.start_time}`);
        // Handle overnight shifts (end < start → next day)
        let end = new Date(`${s.date}T${s.end_time}`);
        if (end <= start) end.setDate(end.getDate() + 1);
        return {
          id:       s.id,
          title:    `${s.worker_name} · ${s.shift_type_name}`,
          start,
          end,
          resource: s,
        };
      }),
    [shifts],
  );

  const eventPropGetter = (event: CalEvent) => {
    const status = event.resource.status.toLowerCase();
    const color  = STATUS_COLORS[status] ?? "#8b9cb3";
    return {
      style: {
        backgroundColor: `${color}28`,
        borderLeft:      `3px solid ${color}`,
        color:           "#e8eef7",
        borderRadius:    "4px",
        fontSize:        "0.75rem",
        padding:         "2px 5px",
      },
    };
  };

  if (shifts.length === 0) {
    return (
      <p style={{ color: "var(--muted)", fontSize: "0.88rem", margin: "0.5rem 0 0" }}>
        No shifts in range — generate some shifts first.
      </p>
    );
  }

  return (
    <div className="rbc-wrap">
      <Calendar<CalEvent>
        localizer={localizer}
        events={events}
        view={view}
        onView={(v) => setView(v)}
        date={date}
        onNavigate={(d) => setDate(d)}
        views={[Views.DAY, Views.WEEK, Views.MONTH]}
        eventPropGetter={eventPropGetter}
        tooltipAccessor={(e) =>
          `${e.resource.worker_name}\n${e.resource.shift_type_name}\n${e.resource.start_time}–${e.resource.end_time}\nStatus: ${e.resource.status}`
        }
        formats={{
          dayHeaderFormat: (date, _culture, localizer) =>
            localizer!.format(date, "EEE dd MMM", "en-US"),
          dayRangeHeaderFormat: ({ start, end }, _culture, localizer) =>
            `${localizer!.format(start, "dd MMM", "en-US")} – ${localizer!.format(end, "dd MMM yyyy", "en-US")}`,
        }}
        style={{ height: 620 }}
      />
    </div>
  );
}
