"use client";

import { useCallback, useEffect, useState } from "react";
import {
  apiGet,
  apiPost,
  apiBase,
  type Department,
  type ShiftRow,
  type ShiftType,
  type Sbu,
} from "@/lib/api";
import { ShiftCalendar } from "@/components/ShiftCalendar";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysISO(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function Home() {
  const [sbus, setSbus] = useState<Sbu[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);
  const [shiftTypes, setShiftTypes] = useState<ShiftType[]>([]);
  const [sbuCode, setSbuCode] = useState("hospitals");
  const [deptCode, setDeptCode] = useState("");
  const [shifts, setShifts] = useState<ShiftRow[]>([]);
  const [listStart, setListStart] = useState(todayISO());
  const [listEnd, setListEnd] = useState(addDaysISO(14));

  const [orchMsg, setOrchMsg] = useState(
    "Generate ICU morning shifts for next week.",
  );
  const [orchOut, setOrchOut] = useState<string | null>(null);
  const [orchErr, setOrchErr] = useState<string | null>(null);

  const [genStart, setGenStart] = useState(todayISO());
  const [genEnd, setGenEnd] = useState(addDaysISO(2));
  const [genShiftIds, setGenShiftIds] = useState("");
  const [genHeadcount, setGenHeadcount] = useState(1);
  const [genOut, setGenOut] = useState<string | null>(null);
  const [genErr, setGenErr] = useState<string | null>(null);

  const [listErr, setListErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Sbu[]>("/meta/sbus")
      .then(setSbus)
      .catch(() => setSbus([]));
  }, []);

  useEffect(() => {
    if (!sbuCode) return;
    apiGet<Department[]>(`/meta/departments?sbu_code=${encodeURIComponent(sbuCode)}`)
      .then((d) => {
        setDepts(d);
        setDeptCode((prev) => {
          if (prev && d.some((x) => x.code === prev)) return prev;
          return d[0]?.code ?? "";
        });
      })
      .catch(() => setDepts([]));
  }, [sbuCode]);

  useEffect(() => {
    if (!sbuCode || !deptCode) return;
    apiGet<ShiftType[]>(
      `/meta/shift-types?sbu_code=${encodeURIComponent(sbuCode)}&department_code=${encodeURIComponent(deptCode)}`,
    )
      .then(setShiftTypes)
      .catch(() => setShiftTypes([]));
  }, [sbuCode, deptCode]);

  const loadShifts = useCallback(async () => {
    if (!sbuCode || !deptCode) return;
    setListErr(null);
    try {
      const q = `/schedule/shifts?sbu_code=${encodeURIComponent(sbuCode)}&department_code=${encodeURIComponent(deptCode)}&start=${listStart}&end=${listEnd}`;
      setShifts(await apiGet<ShiftRow[]>(q));
    } catch (e) {
      setListErr(e instanceof Error ? e.message : "Failed to load shifts");
      setShifts([]);
    }
  }, [sbuCode, deptCode, listStart, listEnd]);

  useEffect(() => {
    loadShifts();
  }, [loadShifts]);

  async function runOrchestrator() {
    setOrchErr(null);
    setOrchOut(null);
    try {
      const r = await apiPost<{
        intent: string;
        routed_to: string;
        extracted_params: Record<string, unknown>;
        sbu_config_loaded: boolean;
      }>("/orchestrator/process", {
        message: orchMsg,
        sbu_code: sbuCode,
        session_id: "web-ui",
      });
      setOrchOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setOrchErr(e instanceof Error ? e.message : "Request failed");
    }
  }

  async function runGenerate() {
    setGenErr(null);
    setGenOut(null);
    try {
      const ids = genShiftIds
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      const body = {
        sbu_code: sbuCode,
        department_code: deptCode,
        date_range_start: genStart,
        date_range_end: genEnd,
        shift_type_ids: ids.length ? ids : [],
        headcount_per_shift: genHeadcount,
        constraints: {},
        session_id: "web-ui",
      };
      const r = await apiPost<{
        slots: Array<{
          date: string;
          shift_type: string;
          assigned_worker: string | null;
          status: string;
          explanation: string;
        }>;
        total_slots: number;
        filled: number;
        escalated: number;
        reasoning_summary: string;
      }>("/schedule/generate", body);
      setGenOut(JSON.stringify(r, null, 2));
      await loadShifts();
    } catch (e) {
      setGenErr(e instanceof Error ? e.message : "Request failed");
    }
  }

  return (
    <>
      <header className="top">
        <h1>AXIS</h1>
        <span>Agentic workforce scheduling · API: {apiBase()}</span>
      </header>
      <main className="wrap">
        <div className="panel">
          <h2>Context</h2>
          <div className="row">
            <label className="field">
              SBU
              <select
                value={sbuCode}
                onChange={(e) => {
                  setSbuCode(e.target.value);
                  setDeptCode("");
                }}
              >
                {sbus.map((s) => (
                  <option key={s.id} value={s.code}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Department
              <select
                value={deptCode}
                onChange={(e) => setDeptCode(e.target.value)}
              >
                {depts.map((d) => (
                  <option key={d.id} value={d.code}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="secondary" onClick={loadShifts}>
              Refresh roster
            </button>
          </div>
          {shiftTypes.length > 0 && (
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
              Shift type IDs (for generator):{" "}
              {shiftTypes.map((st) => `${st.id}=${st.code}`).join(", ")}
            </p>
          )}
        </div>

        <div className="panel">
          <h2>Orchestrator</h2>
          <p style={{ margin: "0 0 0.5rem", color: "var(--muted)", fontSize: "0.9rem" }}>
            Classifies intent and routes to scheduler / swap / direct response. Uses
            DeepSeek when DEEPSEEK_API_KEY is set on the backend.
          </p>
          <label className="field" style={{ width: "100%" }}>
            Manager message
            <textarea value={orchMsg} onChange={(e) => setOrchMsg(e.target.value)} />
          </label>
          <button type="button" className="primary" onClick={runOrchestrator}>
            Process message
          </button>
          {orchErr && <p className="err">{orchErr}</p>}
          {orchOut && <pre className="ok">{orchOut}</pre>}
        </div>

        <div className="panel">
          <h2>Generate schedule</h2>
          <p style={{ margin: "0 0 0.5rem", color: "var(--muted)", fontSize: "0.9rem" }}>
            Calls POST /schedule/generate (deterministic slot fill + validations). Requires
            seeded DB and availability.
          </p>
          <div className="row">
            <label className="field">
              From
              <input
                type="date"
                value={genStart}
                onChange={(e) => setGenStart(e.target.value)}
              />
            </label>
            <label className="field">
              To
              <input
                type="date"
                value={genEnd}
                onChange={(e) => setGenEnd(e.target.value)}
              />
            </label>
            <label className="field">
              Headcount / slot
              <input
                type="number"
                min={1}
                value={genHeadcount}
                onChange={(e) => setGenHeadcount(Number(e.target.value))}
              />
            </label>
          </div>
          <label className="field" style={{ maxWidth: "32rem" }}>
            Shift type IDs (comma-separated, empty = all types in department)
            <input
              value={genShiftIds}
              onChange={(e) => setGenShiftIds(e.target.value)}
              placeholder="e.g. 1,2,3"
            />
          </label>
          <div style={{ marginTop: "0.5rem" }}>
            <button type="button" className="primary" onClick={runGenerate}>
              Run generator
            </button>
          </div>
          {genErr && <p className="err">{genErr}</p>}
          {genOut && <pre className="ok">{genOut}</pre>}
        </div>

        <div className="panel">
          <h2>Roster</h2>
          <div className="row">
            <label className="field">
              List from
              <input
                type="date"
                value={listStart}
                onChange={(e) => setListStart(e.target.value)}
              />
            </label>
            <label className="field">
              List to
              <input
                type="date"
                value={listEnd}
                onChange={(e) => setListEnd(e.target.value)}
              />
            </label>
          </div>
          {listErr && <p className="err">{listErr}</p>}
          <ShiftCalendar shifts={shifts} initialDate={new Date(listStart)} />
        </div>
      </main>
    </>
  );
}
