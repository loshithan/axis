import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X, ChevronUp, ChevronDown, Users } from 'lucide-react';
import { useAxis } from '@/context/AxisContext';

interface Employee {
  id: number;
  employee_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  employee_type: string;
  department_code: string;
  department_name: string;
  sbu_code: string;
  sbu_name: string;
  certifications: string[];
  max_weekly_hours: number;
  weekly_hours_used: number;
  ot_hours: number;
  is_active: boolean;
  created_at: string | null;
}

const EMPLOYEE_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  doctor:     { label: 'Doctor',      className: 'bg-blue-500/15 text-blue-400' },
  nurse:      { label: 'Nurse',       className: 'bg-purple-500/15 text-purple-400' },
  technician: { label: 'Technician',  className: 'bg-orange-500/15 text-orange-400' },
  admin:      { label: 'Admin',       className: 'bg-pink-500/15 text-pink-400' },
};

function EmployeeTypeBadge({ type }: { type: string }) {
  const style = EMPLOYEE_TYPE_STYLES[type] ?? { label: type, className: 'bg-muted text-muted-foreground' };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${style.className}`}>
      {style.label}
    </span>
  );
}

const BASE_URL = (import.meta.env.VITE_API_URL as string) ?? 'http://localhost:8001';

function fetchEmployees(sbu_code: string): Promise<Employee[]> {
  const url = new URL(`${BASE_URL}/employees`);
  if (sbu_code) url.searchParams.set('sbu_code', sbu_code);
  return fetch(url.toString()).then(r => r.json());
}

type SortField = 'name' | 'employee_id' | 'employee_type' | 'department_name' | 'max_weekly_hours';
type SortDir = 'asc' | 'desc';

function DetailModal({ emp, onClose }: { emp: Employee; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{emp.name}</h2>
            <p className="text-sm text-muted-foreground">{emp.employee_id}</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <Row label="SBU" value={emp.sbu_name} />
          <Row label="Department" value={emp.department_name} />
          <Row label="Email" value={emp.email ?? '—'} />
          <Row label="Phone" value={emp.phone ?? '—'} />
          <Row label="Max Weekly Hours" value={`${emp.max_weekly_hours}h`} />
          <Row label="Hours Used (this week)" value={`${emp.weekly_hours_used}h`} />
          <Row label="OT Hours (this week)" value={
            emp.ot_hours > 0
              ? <span className="text-red-400 font-semibold">{emp.ot_hours}h</span>
              : <span className="text-emerald-400">0h</span>
          } />
          <Row label="Status" value={
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${emp.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
              {emp.is_active ? 'Active' : 'Inactive'}
            </span>
          } />
          <Row label="Employee Type" value={<EmployeeTypeBadge type={emp.employee_type} />} />
          <div className="pt-1">
            <div className="text-muted-foreground mb-1.5">Certifications</div>
            <div className="flex flex-wrap gap-1.5">
              {emp.certifications.length === 0
                ? <span className="text-muted-foreground">None</span>
                : emp.certifications.map(c => (
                    <span key={c} className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">{c}</span>
                  ))
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground flex-shrink-0">{label}</span>
      <span className="text-foreground text-right">{value}</span>
    </div>
  );
}

export function EmployeesPage() {
  const { sbuCode } = useAxis();
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [selected, setSelected] = useState<Employee | null>(null);
  const [deptFilter, setDeptFilter] = useState('all');

  const { data: employees = [], isFetching } = useQuery({
    queryKey: ['employees', sbuCode],
    queryFn: () => fetchEmployees(sbuCode),
    enabled: !!sbuCode,
  });

  const departments = ['all', ...Array.from(new Set(employees.map(e => e.department_code))).sort()];

  const filtered = employees
    .filter(e =>
      (deptFilter === 'all' || e.department_code === deptFilter) &&
      (search === '' ||
        e.name.toLowerCase().includes(search.toLowerCase()) ||
        e.employee_id.toLowerCase().includes(search.toLowerCase()) ||
        (e.email ?? '').toLowerCase().includes(search.toLowerCase()))
    )
    .sort((a, b) => {
      const va = a[sortField] ?? '';
      const vb = b[sortField] ?? '';
      const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });

  function toggleSort(field: SortField) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return <ChevronUp className="w-3 h-3 opacity-30" />;
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />;
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <Users className="w-5 h-5 text-primary" />
          <h1 className="font-display font-semibold text-foreground">Employee Management</h1>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {filtered.length} of {employees.length}
          </span>
          {isFetching && <span className="text-xs text-muted-foreground">Loading...</span>}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-border">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search name, ID, email…"
            className="w-full bg-muted border border-border rounded-lg pl-9 pr-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex gap-1.5">
          {departments.map(d => (
            <button
              key={d}
              onClick={() => setDeptFilter(d)}
              className={`text-xs px-3 py-1.5 rounded-lg capitalize transition-colors ${
                deptFilter === d
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:text-foreground'
              }`}
            >
              {d === 'all' ? 'All Depts' : d.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {employees.length === 0 && !isFetching ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No employees found. Select an SBU from the top bar.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {([
                  { field: 'employee_id', label: 'Employee ID' },
                  { field: 'name',        label: 'Name'        },
                  { field: 'employee_type', label: 'Type'      },
                  { field: 'department_name', label: 'Department' },
                  { field: null,          label: 'Certifications' },
                  { field: 'max_weekly_hours', label: 'Max Hrs/Wk' },
                  { field: null,          label: 'Status'      },
                ] as { field: SortField | null; label: string }[]).map(col => (
                  <th
                    key={col.label}
                    className={`pb-3 pr-4 font-medium text-muted-foreground text-xs uppercase tracking-wide ${col.field ? 'cursor-pointer select-none hover:text-foreground' : ''}`}
                    onClick={() => col.field && toggleSort(col.field)}
                  >
                    <div className="flex items-center gap-1">
                      {col.label}
                      {col.field && <SortIcon field={col.field} />}
                    </div>
                  </th>
                ))}
                <th className="pb-3 font-medium text-muted-foreground text-xs uppercase tracking-wide"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(emp => (
                <tr
                  key={emp.id}
                  className="border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer"
                  onClick={() => setSelected(emp)}
                >
                  <td className="py-3 pr-4 text-muted-foreground font-mono text-xs">{emp.employee_id}</td>
                  <td className="py-3 pr-4 font-medium text-foreground">{emp.name}</td>
                  <td className="py-3 pr-4"><EmployeeTypeBadge type={emp.employee_type} /></td>
                  <td className="py-3 pr-4 text-muted-foreground capitalize">{emp.department_name}</td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-1">
                      {emp.certifications.slice(0, 3).map(c => (
                        <span key={c} className="bg-primary/10 text-primary text-xs px-1.5 py-0.5 rounded-full">{c}</span>
                      ))}
                      {emp.certifications.length > 3 && (
                        <span className="bg-muted text-muted-foreground text-xs px-1.5 py-0.5 rounded-full">+{emp.certifications.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-muted-foreground">{emp.max_weekly_hours}h</td>
                  <td className="py-3 pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${emp.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                      {emp.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={e => { e.stopPropagation(); setSelected(emp); }}
                      className="text-xs text-primary hover:underline"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && <DetailModal emp={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
