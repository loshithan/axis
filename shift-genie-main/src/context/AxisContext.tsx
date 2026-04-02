import { createContext, useContext, useState, ReactNode } from 'react';

interface AxisContextValue {
  sbuCode: string;
  setSbuCode: (code: string) => void;
  departmentCode: string;
  setDepartmentCode: (code: string) => void;
  sessionId: string;
}

const AxisContext = createContext<AxisContextValue | null>(null);

export function AxisProvider({ children }: { children: ReactNode }) {
  const [sbuCode, setSbuCode] = useState('hospitals');
  const [departmentCode, setDepartmentCode] = useState('icu');
  const [sessionId] = useState(() => crypto.randomUUID());

  return (
    <AxisContext.Provider value={{ sbuCode, setSbuCode, departmentCode, setDepartmentCode, sessionId }}>
      {children}
    </AxisContext.Provider>
  );
}

export function useAxis() {
  const ctx = useContext(AxisContext);
  if (!ctx) throw new Error('useAxis must be used within AxisProvider');
  return ctx;
}
