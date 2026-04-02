import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2 } from 'lucide-react';
import { fetchSbus, fetchDepartments } from '@/lib/api';
import { useAxis } from '@/context/AxisContext';

export function ContextBar() {
  const { sbuCode, setSbuCode, departmentCode, setDepartmentCode } = useAxis();

  const { data: sbus = [] } = useQuery({
    queryKey: ['sbus'],
    queryFn: fetchSbus,
  });

  const { data: departments = [] } = useQuery({
    queryKey: ['departments', sbuCode],
    queryFn: () => fetchDepartments(sbuCode),
    enabled: !!sbuCode,
  });

  // When SBU changes, reset department to first available
  useEffect(() => {
    if (departments.length > 0 && !departments.find(d => d.code === departmentCode)) {
      setDepartmentCode(departments[0].code);
    }
  }, [departments, departmentCode, setDepartmentCode]);

  return (
    <div className="flex items-center gap-4 px-5 py-2 border-b border-border bg-muted/30 text-sm">
      <Building2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">SBU:</span>
        <select
          value={sbuCode}
          onChange={(e) => setSbuCode(e.target.value)}
          className="bg-background border border-border rounded px-2 py-0.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {sbus.length === 0 && <option value="">Loading...</option>}
          {sbus.map(s => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">Department:</span>
        <select
          value={departmentCode}
          onChange={(e) => setDepartmentCode(e.target.value)}
          disabled={!sbuCode || departments.length === 0}
          className="bg-background border border-border rounded px-2 py-0.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
        >
          {departments.length === 0 && <option value="">Loading...</option>}
          {departments.map(d => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
