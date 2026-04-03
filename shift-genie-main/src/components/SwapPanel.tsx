import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeftRight, AlertTriangle, CheckCircle, Loader2, ChevronDown, ChevronUp, RefreshCw, Clock } from 'lucide-react';
import { OTPanel } from './OTPanel';
import Swal from 'sweetalert2';
import { useAxis } from '@/context/AxisContext';
import {
  fetchLeaveRequests,
  fetchEscalations,
  findSwapCandidates,
  resolveLeaveRequest,
  LeaveRequestItem,
  EscalationItem,
  SwapCandidatesResponse,
} from '@/lib/api';

const RISK_COLOR: Record<string, string> = {
  low: 'text-emerald-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
};

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-amber-500/15 text-amber-400',
  approved: 'bg-blue-500/15 text-blue-400',
  covered: 'bg-emerald-500/15 text-emerald-400',
  rejected: 'bg-red-500/15 text-red-400',
};

function LeaveCard({ item }: { item: LeaveRequestItem }) {
  const [expanded, setExpanded] = useState(false);
  const [candidates, setCandidates] = useState<SwapCandidatesResponse | null>(null);
  const queryClient = useQueryClient();

  const { mutate: loadCandidates, isPending: loadingCandidates } = useMutation({
    mutationFn: () => findSwapCandidates(item.shift_id!),
    onSuccess: (data) => { setCandidates(data); setExpanded(true); },
  });

  const { mutate: resolve, isPending: resolving } = useMutation({
    mutationFn: () => resolveLeaveRequest(item.id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] });
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      const d = data as Record<string, unknown>;
      if (d.status === 'resolved') {
        Swal.fire({
          icon: 'success',
          title: 'Swap Resolved!',
          html: `Replacement: <b>${d.replacement_worker_name}</b><br>Shift #${d.shift_id} created.`,
          confirmButtonColor: '#85409D',
          timer: 3000,
          timerProgressBar: true,
        });
      } else {
        Swal.fire({
          icon: 'warning',
          title: 'No Replacement Found',
          text: 'No available swap candidate passed validation. The shift has been converted to Open and escalated to the manager.',
          confirmButtonColor: '#85409D',
        });
      }
    },
    onError: (err) => {
      Swal.fire({
        icon: 'error',
        title: 'Resolve Failed',
        text: err instanceof Error ? err.message : String(err),
        confirmButtonColor: '#85409D',
      });
    },
  });

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground text-sm">{item.worker_name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[item.status] ?? 'bg-muted text-muted-foreground'}`}>
              {item.status}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {item.date} {item.shift_type_name ? `· ${item.shift_type_name}` : ''}
          </div>
          {item.reason && <div className="text-xs text-muted-foreground mt-1 italic">"{item.reason}"</div>}
        </div>

        {item.status === 'pending' && item.shift_id && (
          <button
            onClick={() => loadCandidates()}
            disabled={loadingCandidates}
            className="flex items-center gap-1.5 text-xs bg-primary/15 text-primary px-3 py-1.5 rounded-lg hover:bg-primary/25 transition-colors disabled:opacity-50 flex-shrink-0"
          >
            {loadingCandidates ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowLeftRight className="w-3 h-3" />}
            Find Swaps
          </button>
        )}

        {item.resolution_summary && (
          <div className="text-xs text-muted-foreground max-w-[200px] text-right">{item.resolution_summary}</div>
        )}
      </div>

      {/* Candidates */}
      {candidates && expanded && (
        <div className="border-t border-border pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {candidates.total_candidates} candidate{candidates.total_candidates !== 1 ? 's' : ''}
            </span>
            <button onClick={() => setExpanded(false)} className="text-muted-foreground hover:text-foreground">
              <ChevronUp className="w-4 h-4" />
            </button>
          </div>

          {candidates.candidates.length === 0 ? (
            <p className="text-xs text-muted-foreground">No eligible swap candidates found.</p>
          ) : (
            <>
              {candidates.candidates.map((c) => (
                <div key={c.worker.id} className="flex items-center justify-between bg-muted/40 rounded-lg px-3 py-2">
                  <div>
                    <div className="text-sm font-medium text-foreground">{c.worker.name}</div>
                    <div className="text-xs text-muted-foreground">{c.reason_ranked}</div>
                  </div>
                  <span className={`text-xs font-semibold uppercase ${RISK_COLOR[c.swap_risk] ?? 'text-muted-foreground'}`}>
                    {c.swap_risk} risk
                  </span>
                </div>
              ))}

              <button
                onClick={async () => {
                  const result = await Swal.fire({
                    title: 'Auto-resolve swap?',
                    text: `Assign the best available candidate to cover ${item.worker_name}'s shift on ${item.date}?`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Resolve',
                    cancelButtonText: 'Cancel',
                    confirmButtonColor: '#85409D',
                    cancelButtonColor: '#9ca3af',
                  });
                  if (result.isConfirmed) resolve();
                }}
                disabled={resolving}
                className="w-full flex items-center justify-center gap-2 text-sm bg-primary text-primary-foreground rounded-lg py-2 hover:opacity-90 transition-opacity disabled:opacity-50 mt-1"
              >
                {resolving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Auto-resolve with best candidate
              </button>
            </>
          )}
        </div>
      )}

      {candidates && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronDown className="w-3 h-3" /> Show {candidates.total_candidates} candidates
        </button>
      )}
    </div>
  );
}

function EscalationCard({ item }: { item: EscalationItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
            <span className="text-sm font-medium text-foreground">{item.shift_type_name ?? 'Unknown shift'}</span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">{item.date}</div>
          <div className="text-xs text-red-400/80 mt-1">{item.description}</div>
        </div>
        <button onClick={() => setExpanded(v => !v)} className="text-muted-foreground hover:text-foreground flex-shrink-0">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      {expanded && (
        <div className="text-xs text-muted-foreground border-t border-border pt-2 leading-relaxed">
          {item.agent_reasoning}
        </div>
      )}
    </div>
  );
}

type Tab = 'leave' | 'escalations' | 'ot';

export function SwapPanel() {
  const [tab, setTab] = useState<Tab>('leave');
  const [statusFilter, setStatusFilter] = useState('pending');
  const { sbuCode, departmentCode } = useAxis();
  const queryClient = useQueryClient();

  const { data: leaveRequests = [], isFetching: fetchingLeave } = useQuery({
    queryKey: ['leave-requests', sbuCode, departmentCode, statusFilter],
    queryFn: () => fetchLeaveRequests(sbuCode, departmentCode, statusFilter),
    enabled: !!sbuCode && !!departmentCode,
    refetchInterval: 5000,
  });

  const { data: escalations = [], isFetching: fetchingEsc } = useQuery({
    queryKey: ['escalations', sbuCode, departmentCode],
    queryFn: () => fetchEscalations(sbuCode, departmentCode),
    enabled: !!sbuCode && !!departmentCode,
    refetchInterval: 10000,
  });

  const isFetching = tab === 'leave' ? fetchingLeave : fetchingEsc;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <ArrowLeftRight className="w-5 h-5 text-primary" />
          <h2 className="font-display font-semibold text-foreground">Swap Management</h2>
          {isFetching && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['leave-requests', 'escalations'] })}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border px-5">
        {([
          { key: 'leave',       label: 'Leave Requests' },
          { key: 'escalations', label: 'Escalations'    },
          { key: 'ot',          label: 'OT Management'  },
        ] as { key: Tab; label: string }[]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`py-2.5 px-1 mr-5 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {label}
            {key === 'leave' && leaveRequests.length > 0 && (
              <span className="ml-1.5 text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded-full">
                {leaveRequests.length}
              </span>
            )}
            {key === 'escalations' && escalations.length > 0 && (
              <span className="ml-1.5 text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full">
                {escalations.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {tab === 'ot' ? (
          <OTPanel />
        ) : !sbuCode || !departmentCode ? (
          <p className="text-sm text-muted-foreground text-center mt-8">
            Select an SBU and department to view swaps.
          </p>
        ) : tab === 'leave' ? (
          <>
            <div className="flex gap-2 mb-1">
              {['pending', 'covered', 'all'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`text-xs px-2.5 py-1 rounded-full capitalize transition-colors ${
                    statusFilter === s
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {leaveRequests.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center mt-8">
                No {statusFilter === 'all' ? '' : statusFilter} leave requests.
              </p>
            ) : (
              leaveRequests.map((item) => <LeaveCard key={item.id} item={item} />)
            )}
          </>
        ) : (
          <>
            {escalations.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center mt-8">
                No open escalations.
              </p>
            ) : (
              escalations.map((item) => <EscalationCard key={item.id} item={item} />)
            )}
          </>
        )}
      </div>
    </div>
  );
}
