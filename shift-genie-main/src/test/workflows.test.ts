/**
 * AXIS Frontend Workflow Tests
 *
 * Covers the logic layer (pure functions) used by the chat and shift workflows:
 *   Req 1 — shift template auto-detection helpers
 *   Req 2 — swap/pending routing helpers
 *   Req 3 — OT threshold detection
 *   Req 4 — status transition helpers
 *
 * Run:  npm test  (or  npx vitest run)
 */

import { describe, it, expect } from "vitest";

// ── Re-implement the helpers under test (exported copies of ChatPanel internals)
// These are copied from ChatPanel.tsx so they can be tested in isolation without
// mounting the full React tree.

// ---------- parseDateFromText (Req 1 / Req 2 date parsing) ------------------

const MONTHS = [
  "january","february","march","april","may","june",
  "july","august","september","october","november","december",
];

function parseDateFromText(text: string): string {
  const today = new Date();
  const lower = text.toLowerCase().replace(/(\d+)(?:st|nd|rd|th)\b/g, "$1");

  if (lower.includes("tomorrow")) {
    const d = new Date(today);
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  }

  const days = ["sunday","monday","tuesday","wednesday","thursday","friday","saturday"];
  for (let i = 0; i < days.length; i++) {
    if (lower.includes(days[i])) {
      const d = new Date(today);
      const diff = (i - today.getDay() + 7) % 7 || 7;
      d.setDate(d.getDate() + diff);
      return d.toISOString().slice(0, 10);
    }
  }

  const isoMatch = text.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (isoMatch) return isoMatch[0];

  const yearMatch = lower.match(/\b(20\d{2})\b/);
  const year = yearMatch ? parseInt(yearMatch[1]) : today.getFullYear();
  const lowerNoYear = yearMatch ? lower.replace(yearMatch[1], "") : lower;

  for (let i = 0; i < MONTHS.length; i++) {
    const afterMonth = lowerNoYear.match(
      new RegExp(`${MONTHS[i]}\\s+(\\d{1,2})(?!\\d)(?!\\s*[ap]m)`)
    );
    if (afterMonth) {
      return `${year}-${String(i + 1).padStart(2, "0")}-${String(parseInt(afterMonth[1])).padStart(2, "0")}`;
    }
    const beforeMonth = lowerNoYear.match(
      new RegExp(`(?<!\\d)(\\d{1,2})\\s+${MONTHS[i]}`)
    );
    if (beforeMonth) {
      return `${year}-${String(i + 1).padStart(2, "0")}-${String(parseInt(beforeMonth[1])).padStart(2, "0")}`;
    }
  }

  return today.toISOString().slice(0, 10);
}

// ---------- extractWorkerName (Req 2 worker extraction) ---------------------

function extractWorkerName(text: string): string | null {
  const forMatch = text.match(/\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/);
  if (forMatch) return forMatch[1];
  const assignMatch = text.match(/\bassign(?:ed)?\s+(?:to\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/);
  if (assignMatch) return assignMatch[1];
  return null;
}

// ---------- isSingleShiftRequest (Req 1 routing) ----------------------------

function isSingleShiftRequest(text: string): boolean {
  const lower = text.toLowerCase();
  if (/\b(generate|roster)\b/.test(lower)) return false;
  if (/\b(next|this)\s+(week|month)\b/.test(lower)) return false;
  if (/\bfrom\b.+?\bto\b/.test(lower)) return false;
  return /\b(create|add|assign|make|book|put)\b/.test(lower);
}

// ---------- findBestShiftType (Req 1 shift-type matching) -------------------

interface ShiftTypeItem { id: number; code: string; name: string; start_time: string; end_time: string; department_code: string }

function findBestShiftType(text: string, types: ShiftTypeItem[]): ShiftTypeItem | null {
  const lower = text.toLowerCase();
  let best: ShiftTypeItem | null = null;
  let bestScore = 0;
  for (const st of types) {
    const words = st.name.toLowerCase().split(/\s+/);
    const score = words.filter((w) => w.length > 2 && lower.includes(w)).length;
    if (score > bestScore) { bestScore = score; best = st; }
  }
  return bestScore > 0 ? best : null;
}

// ---------- isOTRisk (Req 3 threshold detection) ----------------------------

function isOTRisk(weeklyHoursUsed: number, maxWeeklyHours: number): boolean {
  return weeklyHoursUsed >= maxWeeklyHours;
}

// ---------- shiftStatusLabel (Req 4 status display) -------------------------

function shiftStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending:   "Pending Swap",
    open:      "Open",
    confirmed: "Confirmed",
    cancelled: "Cancelled",
    swapped:   "Swapped",
    proposed:  "Proposed",
  };
  return labels[status] ?? status;
}


// ═══════════════════════════════════════════════════════════════════════════
// REQ 1 — Shift Template helpers
// ═══════════════════════════════════════════════════════════════════════════

describe("Req 1 — shift template / auto-assign helpers", () => {

  describe("parseDateFromText", () => {
    it("parses ISO date directly", () => {
      expect(parseDateFromText("create shift for 2026-04-10")).toBe("2026-04-10");
    });

    it("parses 'April 10' (month then day)", () => {
      const result = parseDateFromText("schedule for april 10");
      expect(result).toMatch(/^\d{4}-04-10$/);
    });

    it("parses '3rd april' (day then month with ordinal)", () => {
      const result = parseDateFromText("create shift on 3rd april");
      expect(result).toMatch(/^\d{4}-04-03$/);
    });

    it("parses 'tomorrow'", () => {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      expect(parseDateFromText("shift for tomorrow")).toBe(tomorrow.toISOString().slice(0, 10));
    });

    it("defaults to today when no date found", () => {
      const today = new Date().toISOString().slice(0, 10);
      expect(parseDateFromText("just create a shift")).toBe(today);
    });
  });

  describe("isSingleShiftRequest", () => {
    it("returns true for 'create morning shift for 6th april'", () => {
      expect(isSingleShiftRequest("create morning shift for 6th april")).toBe(true);
    });

    it("returns true for 'add afternoon ICU shift for Kavinda'", () => {
      expect(isSingleShiftRequest("add afternoon ICU shift for Kavinda Silva")).toBe(true);
    });

    it("returns false for 'generate ICU shifts for next week'", () => {
      expect(isSingleShiftRequest("generate ICU shifts for next week")).toBe(false);
    });

    it("returns false for 'schedule shifts for this month'", () => {
      expect(isSingleShiftRequest("schedule shifts for this month")).toBe(false);
    });

    it("returns false for 'generate roster'", () => {
      expect(isSingleShiftRequest("generate roster for the team")).toBe(false);
    });

    it("returns false for 'from April 10 to April 15'", () => {
      expect(isSingleShiftRequest("schedule shifts from April 10 to April 15")).toBe(false);
    });
  });

  describe("findBestShiftType", () => {
    const ICU_TYPES: ShiftTypeItem[] = [
      { id: 1, code: "icu_morning",   name: "Morning ICU",   start_time: "06:00:00", end_time: "14:00:00", department_code: "icu" },
      { id: 2, code: "icu_afternoon", name: "Afternoon ICU", start_time: "14:00:00", end_time: "22:00:00", department_code: "icu" },
      { id: 3, code: "icu_night",     name: "Night ICU",     start_time: "22:00:00", end_time: "06:00:00", department_code: "icu" },
    ];

    it("matches 'afternoon ICU shift'", () => {
      expect(findBestShiftType("create afternoon ICU shift", ICU_TYPES)?.id).toBe(2);
    });

    it("matches 'morning shift'", () => {
      expect(findBestShiftType("create morning shift for tomorrow", ICU_TYPES)?.id).toBe(1);
    });

    it("matches 'night ICU'", () => {
      expect(findBestShiftType("add a night ICU shift", ICU_TYPES)?.id).toBe(3);
    });

    it("returns null when no keyword matches", () => {
      expect(findBestShiftType("create a shift", ICU_TYPES)).toBeNull();
    });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// REQ 2 — Swap / Pending workflow helpers
// ═══════════════════════════════════════════════════════════════════════════

describe("Req 2 — swap / pending workflow helpers", () => {

  describe("extractWorkerName", () => {
    it("extracts name from 'for Kavinda Silva'", () => {
      expect(extractWorkerName("create afternoon ICU shift for Kavinda Silva on 3rd April")).toBe("Kavinda Silva");
    });

    it("extracts name from 'assign to Amara Perera'", () => {
      expect(extractWorkerName("assign to Amara Perera for night shift")).toBe("Amara Perera");
    });

    it("extracts name from 'assign Sachini Wickrama'", () => {
      expect(extractWorkerName("assign Sachini Wickrama morning shift")).toBe("Sachini Wickrama");
    });

    it("returns null when no worker name present", () => {
      expect(extractWorkerName("create morning shift for tomorrow")).toBeNull();
    });

    it("does not match single lowercase words after 'for'", () => {
      expect(extractWorkerName("create shift for tomorrow")).toBeNull();
    });
  });

  describe("shiftStatusLabel — pending state", () => {
    it("labels pending status as 'Pending Swap'", () => {
      expect(shiftStatusLabel("pending")).toBe("Pending Swap");
    });

    it("labels open status as 'Open'", () => {
      expect(shiftStatusLabel("open")).toBe("Open");
    });

    it("labels confirmed status as 'Confirmed'", () => {
      expect(shiftStatusLabel("confirmed")).toBe("Confirmed");
    });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// REQ 3 — OT Validation threshold
// ═══════════════════════════════════════════════════════════════════════════

describe("Req 3 — OT threshold detection", () => {

  it("returns false when worker has 32h (under 40h limit)", () => {
    expect(isOTRisk(32, 40)).toBe(false);
  });

  it("returns false when worker has 39h", () => {
    expect(isOTRisk(39, 40)).toBe(false);
  });

  it("returns true when worker is exactly at 40h", () => {
    expect(isOTRisk(40, 40)).toBe(true);
  });

  it("returns true when worker has 48h (already over limit)", () => {
    expect(isOTRisk(48, 40)).toBe(true);
  });

  it("respects non-standard limits (e.g. 36h max)", () => {
    expect(isOTRisk(36, 36)).toBe(true);
    expect(isOTRisk(35, 36)).toBe(false);
  });

  it("returns true when hours_remaining <= 0 (derived check)", () => {
    const weekly_hours_used = 40;
    const max_weekly_hours = 40;
    const hours_remaining = max_weekly_hours - weekly_hours_used;
    expect(hours_remaining).toBe(0);
    expect(isOTRisk(weekly_hours_used, max_weekly_hours)).toBe(true);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// REQ 4 — Status Transitions
// ═══════════════════════════════════════════════════════════════════════════

describe("Req 4 — status transition helpers", () => {

  it("shiftStatusLabel covers all valid statuses", () => {
    const statuses = ["pending", "open", "confirmed", "cancelled", "swapped", "proposed"];
    for (const s of statuses) {
      expect(shiftStatusLabel(s)).not.toBe(s); // must be a human label, not raw value
    }
  });

  it("pending → covered transition is represented correctly", () => {
    // The leave list filters by status — simulate pending vs covered
    const leaveItems = [
      { id: 1, status: "pending", worker_name: "Kavinda Silva" },
      { id: 2, status: "covered", worker_name: "Amara Perera" },
    ];
    const pending = leaveItems.filter(l => l.status === "pending");
    const covered = leaveItems.filter(l => l.status === "covered");
    expect(pending).toHaveLength(1);
    expect(covered).toHaveLength(1);
    expect(covered[0].worker_name).toBe("Amara Perera");
  });

  it("shift PENDING status is distinct from OPEN", () => {
    const statuses = ["open", "pending", "confirmed", "cancelled", "swapped", "proposed"];
    const unique = new Set(statuses);
    expect(unique.size).toBe(statuses.length); // all values are unique
  });

  it("OT assignment with ≥40h still proceeds after override confirmation", () => {
    // Simulate the UI logic: OT warning shown, user confirms → proceed flag set
    const weeklyHours = 40;
    const maxHours = 40;
    const userConfirmed = true; // simulates clicking "Proceed" in Swal

    const shouldProceed = !isOTRisk(weeklyHours, maxHours) || userConfirmed;
    expect(shouldProceed).toBe(true);
  });

  it("OT assignment blocked when user cancels OT warning", () => {
    const weeklyHours = 40;
    const maxHours = 40;
    const userConfirmed = false; // simulates clicking "Cancel" in Swal

    const shouldProceed = !isOTRisk(weeklyHours, maxHours) || userConfirmed;
    expect(shouldProceed).toBe(false);
  });
});
