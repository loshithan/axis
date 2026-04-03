import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Clock, Bell, CheckCircle, ChevronDown, ChevronUp, Loader2, UserCheck, X } from 'lucide-react';
import Swal from 'sweetalert2';
import { useAxis } from '@/context/AxisContext';
import {
  fetchOTRequests,
  fetchOTApplications,
  fetchOTWorkers,
  notifyOTWorkers,
  applyForOT,
  assignFirstOTApplicant,
  OTRequestItem,
  OTApplicationItem,
  OTWorkerItem,
} from '@/lib/api';

const STATUS_BADGE: Record<string, string> = {
  open:     'bg-amber-500/15 text-amber-400',
  notified: 'bg-blue-500/15 text-blue-400',
  assigned: 'bg-emerald-500/15 text-emerald-400',
  cancelled:'bg-red-500/15 text-red-400',
};

const APP_STATUS_BADGE: Record<string, string> = {
  pending:  'bg-amber-500/15 text-amber-400',
  assigned: 'bg-emerald-500/15 text-emerald-400',
  rejected: 'bg-muted text-muted-foreground',
};

function hoursBar(used: number, max: number) {
  const pct = Math.min(100, (used / max) * 100);
  const color = pct >= 100 ? 'bg-red-500' : pct >= 75 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-muted-foreground">{used}h / {max}h</span>
    </div>
  );
}

// ── Notify Workers Modal ──────────────────────────────────────────────
function NotifyModal({
  otRequest,
  onClose,
}: {
  otRequest: OTRequestItem;
  onClose: () => void;
}) {
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: workers = [], isFetching } = useQuery({
    queryKey: ['ot-workers', sbuCode, departmentCode, otRequest.date],
    queryFn: () => fetchOTWorkers(sbuCode, departmentCode, otRequest.date),
    enabled: !!sbuCode && !!departmentCode,
  });

  const { mutate: notify, isPending } = useMutation({
    mutationFn: () => notifyOTWorkers(otRequest.id, Array.from(selected)),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ot-requests'] });
      queryClient.invalidateQueries({ queryKey: ['ot-applications', otRequest.id] });
      Swal.fire({
        icon: 'success',
        title: 'Workers Notified',
        text: `${data.workers_notified} worker(s) have been notified about this OT opportunity.`,
        confirmButtonColor: '#85409D',
        timer: 2500,
        timerProgressBar: true,
      });
      onClose();
    },
    onError: (err) => {
      Swal.fire({ icon: 'error', title: 'Failed', text: err instanceof Error ? err.message : String(err), confirmButtonColor: '#85409D' });
    },
  });

  function toggleWorker(id: number) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-5 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-foreground">Notify Staff for OT</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {otRequest.shift_type_name} · {otRequest.date} · {otRequest.start_time.slice(0,5)}–{otRequest.end_time.slice(0,5)}
            </p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>

        <div className="text-xs text-muted-foreground">Select employees to notify. Workers sorted by available hours remaining.</div>

        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {isFetching ? (
            <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
          ) : workers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No workers found in this department.</p>
          ) : (
            workers.map((w: OTWorkerItem) => (
              <label
                key={w.id}
                className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors ${
                  selected.has(w.id) ? 'bg-primary/10 border border-primary/30' : 'bg-muted/40 hover:bg-muted/60'
                }`}
              >
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={selected.has(w.id)}
                  onChange={() => toggleWorker(w.id)}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{w.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground capitalize">{w.employee_type}</span>
                    {hoursBar(w.weekly_hours_used, w.max_weekly_hours)}
                  </div>
                </div>
                {w.hours_remaining <= 0 && (
                  <span className="text-xs text-red-400 font-medium flex-shrink-0">OT</span>
                )}
              </label>
            ))
          )}
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground">{selected.size} selected</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg transition-colors">
              Cancel
            </button>
            <button
              onClick={() => notify()}
              disabled={selected.size === 0 || isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bell className="w-3.5 h-3.5" />}
              Notify Staff for OT
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── OT Request Card ───────────────────────────────────────────────────
function OTRequestCard({ item }: { item: OTRequestItem }) {
  const [expanded, setExpanded] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: applications = [], isFetching: fetchingApps } = useQuery({
    queryKey: ['ot-applications', item.id],
    queryFn: () => fetchOTApplications(item.id),
    enabled: expanded,
    refetchInterval: expanded ? 5000 : false,
  });

  const { mutate: apply, isPending: applying } = useMutation({
    mutationFn: (worker_id: number) => applyForOT(item.id, worker_id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ot-applications', item.id] });
      queryClient.invalidateQueries({ queryKey: ['ot-requests'] });
      Swal.fire({
        icon: 'success',
        title: 'Application Recorded',
        text: `Queue position: #${data.queue_position}`,
        confirmButtonColor: '#85409D',
        timer: 2000,
        timerProgressBar: true,
      });
    },
    onError: (err) => {
      Swal.fire({ icon: 'warning', title: 'Already Applied', text: err instanceof Error ? err.message : String(err), confirmButtonColor: '#85409D' });
    },
  });

  const { mutate: assignFirst, isPending: assigning } = useMutation({
    mutationFn: () => assignFirstOTApplicant(item.id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ot-requests'] });
      queryClient.invalidateQueries({ queryKey: ['ot-applications', item.id] });
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      Swal.fire({
        icon: 'success',
        title: 'OT Shift Assigned!',
        html: `
          <div style="text-align:left;font-size:14px;line-height:1.8">
            <b>Worker:</b> ${data.assigned_worker_name}<br>
            <b>Rejected:</b> ${data.rejected_count} other applicant(s)<br>
            ${!data.validation_passed ? '<span style="color:#f59e0b">⚠️ Note: Worker may exceed weekly hours limit (OT approved).</span>' : ''}
          </div>
        `,
        confirmButtonColor: '#85409D',
        timer: 3000,
        timerProgressBar: true,
      });
    },
    onError: (err) => {
      Swal.fire({ icon: 'error', title: 'Assignment Failed', text: err instanceof Error ? err.message : String(err), confirmButtonColor: '#85409D' });
    },
  });

  const pendingApps = applications.filter(a => a.status === 'pending');
  const isAssigned = item.status === 'assigned';

  return (
    <>
      <div className={`rounded-lg border p-4 space-y-3 ${isAssigned ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-border bg-card'}`}>
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-foreground text-sm">{item.shift_type_name ?? 'Unknown shift'}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[item.status] ?? 'bg-muted text-muted-foreground'}`}>
                {item.status}
              </span>
              {item.application_count > 0 && !isAssigned && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/15 text-primary font-medium">
                  {item.application_count} applicant{item.application_count !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {item.date} · {item.start_time.slice(0,5)}–{item.end_time.slice(0,5)}
              {item.leave_request_id && <span className="ml-2 text-amber-400">Leave #{item.leave_request_id}</span>}
            </div>
            {isAssigned && item.assigned_worker_name && (
              <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                <UserCheck className="w-3 h-3" />
                Assigned to {item.assigned_worker_name}
              </div>
            )}
          </div>

          {/* Actions */}
          {!isAssigned && (
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <button
                onClick={() => setNotifyOpen(true)}
                className="flex items-center gap-1 text-xs bg-blue-500/15 text-blue-400 px-2.5 py-1.5 rounded-lg hover:bg-blue-500/25 transition-colors"
              >
                <Bell className="w-3 h-3" />
                Notify
              </button>
              <button
                onClick={() => setExpanded(v => !v)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          )}
        </div>

        {/* Application Queue */}
        {expanded && (
          <div className="border-t border-border pt-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Application Queue (FIFO)
              </span>
              {fetchingApps && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
            </div>

            {applications.length === 0 ? (
              <p className="text-xs text-muted-foreground">No applications yet. Notify staff to start the queue.</p>
            ) : (
              <div className="space-y-1.5">
                {applications.map((app: OTApplicationItem, idx) => (
                  <div key={app.id} className={`flex items-center gap-3 rounded-lg px-3 py-2 ${
                    app.status === 'assigned' ? 'bg-emerald-500/10' : app.status === 'rejected' ? 'opacity-50 bg-muted/20' : 'bg-muted/40'
                  }`}>
                    {app.status === 'pending' && (
                      <span className="text-xs font-bold text-primary w-4">#{idx + 1}</span>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{app.worker_name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {hoursBar(app.weekly_hours_used, app.max_weekly_hours)}
                        {app.applied_at && (
                          <span className="text-xs text-muted-foreground">
                            {new Date(app.applied_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${APP_STATUS_BADGE[app.status] ?? ''}`}>
                      {app.status}
                    </span>
                    {/* Apply on behalf of notified worker (MVP simulation) */}
                    {app.status === 'pending' && !app.applied_at?.includes('T') === false && app.notified_at && !app.applied_at ? (
                      <button
                        onClick={() => apply(app.worker_id)}
                        disabled={applying}
                        className="text-xs text-primary hover:underline disabled:opacity-50 flex-shrink-0"
                      >
                        Apply
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            )}

            {/* Assign First Applicant */}
            {pendingApps.length > 0 && (
              <button
                onClick={async () => {
                  const first = pendingApps[0];
                  const result = await Swal.fire({
                    title: 'Assign First Applicant?',
                    html: `Assign <b>${first.worker_name}</b> to this OT shift?<br><small>${pendingApps.length - 1} other applicant(s) will be rejected.</small>`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Assign',
                    cancelButtonText: 'Cancel',
                    confirmButtonColor: '#85409D',
                    cancelButtonColor: '#9ca3af',
                  });
                  if (result.isConfirmed) assignFirst();
                }}
                disabled={assigning}
                className="w-full flex items-center justify-center gap-2 text-sm bg-primary text-primary-foreground rounded-lg py-2 hover:opacity-90 disabled:opacity-50 transition-opacity mt-1"
              >
                {assigning ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Assign First Applicant ({pendingApps[0]?.worker_name})
              </button>
            )}

            {/* Apply on behalf of notified-but-not-applied workers */}
            {applications.filter(a => a.status === 'pending' && a.notified_at).length > 0 && (
              <div className="border-t border-border pt-2">
                <p className="text-xs text-muted-foreground mb-1.5">Record OT application on behalf of notified staff:</p>
                <div className="flex flex-wrap gap-1.5">
                  {applications
                    .filter(a => a.status === 'pending' && a.notified_at)
                    .map(a => (
                      <button
                        key={a.id}
                        onClick={() => apply(a.worker_id)}
                        disabled={applying}
                        className="text-xs bg-muted hover:bg-muted/80 text-foreground px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {a.worker_name} applied
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {notifyOpen && <NotifyModal otRequest={item} onClose={() => setNotifyOpen(false)} />}
    </>
  );
}

// ── Main OT Panel ─────────────────────────────────────────────────────
export function OTPanel() {
  const [statusFilter, setStatusFilter] = useState('open');
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();

  const { data: otRequests = [], isFetching } = useQuery({
    queryKey: ['ot-requests', sbuCode, departmentCode, statusFilter],
    queryFn: () => fetchOTRequests(sbuCode, departmentCode, statusFilter),
    enabled: !!sbuCode && !!departmentCode,
    refetchInterval: 10000,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">OT Management</span>
          {isFetching && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['ot-requests'] })}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* How it works banner */}
      <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-primary/8 border border-primary/20 text-xs text-muted-foreground leading-relaxed">
        <span className="text-primary font-medium">Flow: </span>
        OT requests are created automatically when a leave has no eligible swap (&lt;40hr) candidate.
        Notify staff → they apply (FIFO) → assign the first applicant.
      </div>

      {/* Status filter */}
      <div className="flex gap-1.5 px-4 py-3">
        {['open', 'notified', 'assigned', 'all'].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`text-xs px-2.5 py-1 rounded-full capitalize transition-colors ${
              statusFilter === s ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-3">
        {!sbuCode || !departmentCode ? (
          <p className="text-sm text-muted-foreground text-center mt-8">Select an SBU and department to view OT requests.</p>
        ) : otRequests.length === 0 ? (
          <div className="text-center mt-8 space-y-1">
            <p className="text-sm text-muted-foreground">No {statusFilter === 'all' ? '' : statusFilter} OT requests.</p>
            <p className="text-xs text-muted-foreground">OT requests are created automatically when a leave swap can't be filled within the 40-hour limit.</p>
          </div>
        ) : (
          otRequests.map(item => <OTRequestCard key={item.id} item={item} />)
        )}
      </div>
    </div>
  );
}
