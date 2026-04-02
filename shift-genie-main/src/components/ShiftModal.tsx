import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Loader2, Trash2, Save, UserX } from 'lucide-react';
import Swal from 'sweetalert2';
import { useAxis } from '@/context/AxisContext';
import {
  fetchWorkersList,
  fetchShiftTypesList,
  createShiftManual,
  updateShift,
  deleteShift,
  ShiftListItem,
} from '@/lib/api';

interface ShiftModalProps {
  mode: 'create' | 'edit';
  /** Pre-filled date for create mode (YYYY-MM-DD) */
  initialDate?: string;
  /** Existing shift data for edit mode */
  shift?: ShiftListItem;
  onClose: () => void;
  onSaved: () => void;
}

function toHHMM(timeStr: string): string {
  return timeStr.slice(0, 5); // "HH:MM:SS" → "HH:MM"
}

function toHHMMSS(timeStr: string): string {
  return timeStr.length === 5 ? `${timeStr}:00` : timeStr;
}

export function ShiftModal({ mode, initialDate, shift, onClose, onSaved }: ShiftModalProps) {
  const { sbuCode, departmentCode } = useAxis();

  const today = new Date().toISOString().slice(0, 10);

  const [date, setDate] = useState(
    mode === 'edit' ? shift?.date ?? today : initialDate ?? today,
  );
  const [shiftTypeId, setShiftTypeId] = useState<number | ''>(
    mode === 'edit' && shift ? shift.shift_type_id : '',
  );
  const [workerId, setWorkerId] = useState<number | null | ''>(
    mode === 'edit' ? (shift?.worker_id ?? null) : '',
  );
  const [startTime, setStartTime] = useState(
    mode === 'edit' ? toHHMM(shift?.start_time ?? '08:00:00') : '08:00',
  );
  const [endTime, setEndTime] = useState(
    mode === 'edit' ? toHHMM(shift?.end_time ?? '16:00:00') : '16:00',
  );
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const { data: shiftTypes = [] } = useQuery({
    queryKey: ['shift-types', sbuCode, departmentCode],
    queryFn: () => fetchShiftTypesList(sbuCode, departmentCode),
    enabled: !!sbuCode && !!departmentCode,
  });

  const { data: workers = [] } = useQuery({
    queryKey: ['workers-list', sbuCode, departmentCode],
    queryFn: () => fetchWorkersList(sbuCode, departmentCode),
    enabled: !!sbuCode && !!departmentCode,
  });

  // In edit mode, if the shift type changes and user hasn't edited times yet, sync times from type
  const [timesTouched, setTimesTouched] = useState(false);

  // When shift type changes, pre-fill times if user hasn't edited them
  function handleShiftTypeChange(id: number | '') {
    setShiftTypeId(id);
    if (id !== '' && !timesTouched) {
      const st = shiftTypes.find(s => s.id === id);
      if (st) {
        setStartTime(toHHMM(st.start_time));
        setEndTime(toHHMM(st.end_time));
      }
    }
  }

  async function handleSave() {
    if (shiftTypeId === '') {
      Swal.fire({ icon: 'warning', title: 'Shift type required', text: 'Please select a shift type.', confirmButtonColor: '#85409D' });
      return;
    }
    if (!date) {
      Swal.fire({ icon: 'warning', title: 'Date required', text: 'Please select a date.', confirmButtonColor: '#85409D' });
      return;
    }

    const workerName = workerId ? workers.find(w => w.id === workerId)?.name ?? '' : 'Open Shift';
    const stName = shiftTypes.find(s => s.id === shiftTypeId)?.name ?? '';

    const result = await Swal.fire({
      title: mode === 'create' ? 'Create Shift?' : 'Save Changes?',
      html: `
        <div style="text-align:left;font-size:14px;line-height:1.8">
          <b>Date:</b> ${date}<br>
          <b>Shift Type:</b> ${stName}<br>
          <b>Worker:</b> ${workerName}<br>
          <b>Time:</b> ${startTime} – ${endTime}
        </div>
      `,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: mode === 'create' ? 'Create' : 'Save',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#85409D',
      cancelButtonColor: '#9ca3af',
    });

    if (!result.isConfirmed) return;

    setSaving(true);
    try {
      const body = {
        worker_id: workerId === '' ? null : (workerId as number | null),
        shift_type_id: shiftTypeId as number,
        date,
        start_time: toHHMMSS(startTime),
        end_time: toHHMMSS(endTime),
      };

      if (mode === 'create') {
        await createShiftManual(body);
      } else {
        await updateShift(shift!.id, body);
      }

      await Swal.fire({
        icon: 'success',
        title: mode === 'create' ? 'Shift Created!' : 'Shift Updated!',
        text: workerId ? `${workerName} has been assigned to this shift.` : 'Open shift saved successfully.',
        confirmButtonColor: '#85409D',
        timer: 2000,
        timerProgressBar: true,
      });

      onSaved();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const isConflict = msg.includes('409') || msg.toLowerCase().includes('conflict');
      Swal.fire({
        icon: isConflict ? 'warning' : 'error',
        title: isConflict ? 'Schedule Conflict Detected' : 'Error',
        text: isConflict
          ? msg.replace(/.*Conflict:\s*/i, '')
          : msg,
        confirmButtonColor: '#85409D',
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    const result = await Swal.fire({
      title: 'Delete this shift?',
      text: 'This action cannot be undone.',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#ef4444',
      cancelButtonColor: '#9ca3af',
    });

    if (!result.isConfirmed) return;

    setDeleting(true);
    try {
      await deleteShift(shift!.id);
      await Swal.fire({
        icon: 'success',
        title: 'Shift Deleted',
        timer: 1500,
        timerProgressBar: true,
        showConfirmButton: false,
      });
      onSaved();
      onClose();
    } catch (err) {
      Swal.fire({
        icon: 'error',
        title: 'Delete Failed',
        text: err instanceof Error ? err.message : String(err),
        confirmButtonColor: '#85409D',
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md mx-4 p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="font-display font-semibold text-foreground text-lg">
            {mode === 'create' ? 'Create Shift' : 'Edit Shift'}
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Date */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Date</label>
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* Shift Type */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Shift Type</label>
          <select
            value={shiftTypeId}
            onChange={e => handleShiftTypeChange(e.target.value === '' ? '' : Number(e.target.value))}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">Select shift type…</option>
            {shiftTypes.map(st => (
              <option key={st.id} value={st.id}>{st.name}</option>
            ))}
          </select>
        </div>

        {/* Worker */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-foreground">Assigned Worker</label>
          <select
            value={workerId === null ? 'open' : (workerId === '' ? '' : String(workerId))}
            onChange={e => {
              if (e.target.value === 'open') setWorkerId(null);
              else if (e.target.value === '') setWorkerId('');
              else setWorkerId(Number(e.target.value));
            }}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">Select worker…</option>
            <option value="open">— Open Shift (unassigned) —</option>
            {workers.map(w => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
          {workerId === null && (
            <p className="flex items-center gap-1.5 text-xs text-amber-600">
              <UserX className="w-3.5 h-3.5" />
              This shift will be created as open and will appear unassigned on the calendar.
            </p>
          )}
        </div>

        {/* Time Range */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">Start Time</label>
            <input
              type="time"
              value={startTime}
              onChange={e => { setStartTime(e.target.value); setTimesTouched(true); }}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">End Time</label>
            <input
              type="time"
              value={endTime}
              onChange={e => { setEndTime(e.target.value); setTimesTouched(true); }}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          {mode === 'edit' ? (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600 disabled:opacity-50 transition-colors"
            >
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Delete Shift
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {mode === 'create' ? 'Create' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

