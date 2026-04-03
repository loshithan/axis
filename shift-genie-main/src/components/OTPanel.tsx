import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCircle, ChevronDown, ChevronUp, Clock, Loader2, RefreshCw } from 'lucide-react';
import Swal from 'sweetalert2';
import { useAxis } from '@/context/AxisContext';
import {
  assignOTWorker,
  fetchOTApplications,
  fetchOTRequests,
  fetchOTWorkersForShift,
  notifyOTWorkers,
  OTRequestItem,
  OTWorkerItem,
} from '@/lib/api';

const STATUS_BADGE: Record<string, string> = {
  open: 'bg-amber-500/15 text-amber-400',
  notified: 'bg-blue-500/15 text-blue-400',
  assigned: 'bg-emerald-500/15 text-emerald-400',
  cancelled: 'bg-red-500/15 text-red-400',
};

function hoursLabel(w: OTWorkerItem): string {
  return `${w.name} (${w.employee_type}) - ${w.weekly_hours_used}h/${w.max_weekly_hours}h`;
}

function OTRequestCard({ item }: { item: OTRequestItem }) {
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState<number | ''>('');

  const { data: workers = [], isFetching: loadingWorkers } = useQuery({
    queryKey: ['ot-workers', item.id, sbuCode, departmentCode, item.date],
    queryFn: () => fetchOTWorkersForShift(sbuCode, departmentCode, item.date, item.shift_id),
    enabled: !!sbuCode && !!departmentCode,
  });

  const { data: applications = [], isFetching: loadingApps } = useQuery({
    queryKey: ['ot-applications', item.id],
    queryFn: () => fetchOTApplications(item.id),
    enabled: expanded,
    refetchInterval: expanded ? 5000 : false,
  });

  const { mutate: notifyAll, isPending: notifying } = useMutation({
    mutationFn: () => notifyOTWorkers(item.id, workers.map((w) => w.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ot-requests'] });
      queryClient.invalidateQueries({ queryKey: ['ot-applications', item.id] });
      Swal.fire({
        icon: 'success',
        title: 'Staff Notified',
        text: `${workers.length} eligible staff notified for this open shift.`,
        confirmButtonColor: '#85409D',
        timer: 1800,
        timerProgressBar: true,
      });
    },
    onError: (err) => {
      Swal.fire({
        icon: 'error',
        title: 'Notify Failed',
        text: err instanceof Error ? err.message : String(err),
        confirmButtonColor: '#85409D',
      });
    },
  });


  const { mutate: assignSelected, isPending: assigningSelected } = useMutation({
    mutationFn: (workerId: number) => assignOTWorker(item.id, workerId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ot-requests'] });
      queryClient.invalidateQueries({ queryKey: ['ot-applications', item.id] });
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      Swal.fire({
        icon: 'success',
        title: 'Shift Assigned',
        text: `Assigned to ${data.assigned_worker_name}`,
        confirmButtonColor: '#85409D',
        timer: 2000,
        timerProgressBar: true,
      });
    },
    onError: (err) => {
      Swal.fire({
        icon: 'error',
        title: 'Assign Failed',
        text: err instanceof Error ? err.message : String(err),
        confirmButtonColor: '#85409D',
      });
    },
  });

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground text-sm">{item.shift_type_name ?? 'Open shift'}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[item.status] ?? 'bg-muted text-muted-foreground'}`}>
              {item.status}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {item.date} · {item.start_time.slice(0, 5)}-{item.end_time.slice(0, 5)}
          </div>
          {item.required_employee_type && (
            <div className="text-xs text-primary mt-1">Required role: {item.required_employee_type}</div>
          )}
          {item.assigned_worker_name && (
            <div className="text-xs text-emerald-400 mt-1">Assigned: {item.assigned_worker_name}</div>
          )}
        </div>

        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {item.status === 'open' && (
        <button
          onClick={() => notifyAll()}
          disabled={notifying || loadingWorkers || workers.length === 0}
          className="flex items-center gap-1.5 text-xs bg-blue-500/15 text-blue-400 px-3 py-2 rounded-lg hover:bg-blue-500/25 transition-colors disabled:opacity-50 w-full justify-center"
        >
          {notifying ? <Loader2 className="w-3 h-3 animate-spin" /> : <Bell className="w-3 h-3" />}
          {loadingWorkers ? 'Loading...' : `Notify All Eligible${workers.length > 0 ? ` (${workers.length})` : ''}`}
        </button>
      )}

      {item.status === 'notified' && (
        <div className="flex items-center gap-2">
          <select
            value={selectedWorkerId}
            onChange={(e) => setSelectedWorkerId(e.target.value ? Number(e.target.value) : '')}
            className="flex-1 h-9 rounded-md border border-border bg-background px-2 text-sm"
            disabled={loadingWorkers || assigningSelected}
          >
            <option value="">Select staff to assign...</option>
            {workers.map((w) => (
              <option key={w.id} value={w.id}>{hoursLabel(w)}</option>
            ))}
          </select>
          <button
            onClick={() => selectedWorkerId && assignSelected(selectedWorkerId)}
            disabled={!selectedWorkerId || assigningSelected || loadingWorkers}
            className="flex items-center gap-1.5 text-xs bg-primary text-primary-foreground px-3 py-2 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {assigningSelected ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
            Assign
          </button>
        </div>
      )}

      {expanded && (
        <div className="border-t border-border pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Notified Staff</span>
            {loadingApps && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
          </div>

          {applications.length === 0 ? (
            <p className="text-xs text-muted-foreground">No staff notified yet. Use Notify above to invite staff.</p>
          ) : (
            applications.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2 gap-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{a.worker_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {a.weekly_hours_used}h/{a.max_weekly_hours}h ·{' '}
                    <span className={a.status === 'assigned' ? 'text-emerald-400' : a.status === 'rejected' ? 'text-red-400' : 'text-amber-400'}>
                      {a.status}
                    </span>
                  </div>
                </div>
                <div className="text-xs text-muted-foreground shrink-0">
                  {a.notified_at ? new Date(a.notified_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}
                </div>
                {a.status === 'pending' && item.status !== 'assigned' && (
                  <button
                    onClick={() => assignSelected(a.worker_id)}
                    disabled={assigningSelected}
                    className="flex items-center gap-1 text-xs bg-emerald-500/15 text-emerald-400 px-2.5 py-1.5 rounded-md hover:bg-emerald-500/25 transition-colors disabled:opacity-50 shrink-0"
                  >
                    {assigningSelected ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                    Accept
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function OTPanel() {
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();

  const { data: otRequests = [], isFetching } = useQuery({
    queryKey: ['ot-requests', sbuCode, departmentCode, 'all'],
    queryFn: () => fetchOTRequests(sbuCode, departmentCode, 'all'),
    enabled: !!sbuCode && !!departmentCode,
    refetchInterval: 10000,
  });

  const openItems = useMemo(() => otRequests.filter((r) => r.status === 'open'), [otRequests]);
  const notifiedItems = useMemo(() => otRequests.filter((r) => r.status === 'notified'), [otRequests]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Open Shifts</span>
          {isFetching && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['ot-requests'] })}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {!sbuCode || !departmentCode ? (
          <p className="text-sm text-muted-foreground text-center mt-8">Select an SBU and department to view open shifts.</p>
        ) : (
          <>
            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Open</h3>
              {openItems.length === 0 ? (
                <p className="text-sm text-muted-foreground">No open shifts.</p>
              ) : (
                openItems.map((item) => <OTRequestCard key={item.id} item={item} />)
              )}
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Notified</h3>
              {notifiedItems.length === 0 ? (
                <p className="text-sm text-muted-foreground">No notified shifts.</p>
              ) : (
                notifiedItems.map((item) => <OTRequestCard key={item.id} item={item} />)
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
