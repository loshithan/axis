import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { ChatMessage } from '@/types/shift';
import { useAxis } from '@/context/AxisContext';
import { orchestratorProcess, generateSchedule, searchWorker, fetchShifts, fetchShiftTypesList, createShiftManual, createLeaveRequest, ScheduleSlotResult, ShiftTypeItem } from '@/lib/api';

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: `👋 **Welcome to AXIS ShiftAI!**\n\nI'm your AI scheduling assistant connected to the AXIS backend.\n\n**Try saying:**\n- "Schedule ICU shifts for next week"\n- "Generate shifts for this month"\n- "Assign emergency department shifts for tomorrow"\n- "Create shifts for April 10 to April 15"`,
};

const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june',
  'july', 'august', 'september', 'october', 'november', 'december'];

function parseDateFromText(text: string): string {
  const today = new Date();
  // strip ordinal suffixes: "7th" → "7", "1st" → "1", "22nd" → "22"
  const lower = text.toLowerCase().replace(/(\d+)(?:st|nd|rd|th)\b/g, '$1');

  if (lower.includes('tomorrow')) {
    const d = new Date(today);
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  }

  const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
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

  const slashDate = text.match(/(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
  if (slashDate) {
    const y = slashDate[3]
      ? slashDate[3].length === 2 ? 2000 + parseInt(slashDate[3]) : parseInt(slashDate[3])
      : today.getFullYear();
    const m = String(parseInt(slashDate[1])).padStart(2, '0');
    const day = String(parseInt(slashDate[2])).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  // extract explicit 4-digit year if present (e.g. "7 april 2026")
  const yearMatch = lower.match(/\b(20\d{2})\b/);
  const year = yearMatch ? parseInt(yearMatch[1]) : today.getFullYear();
  // remove the year token so it doesn't get mistaken for a day number
  const lowerNoYear = yearMatch ? lower.replace(yearMatch[1], '') : lower;

  for (let i = 0; i < MONTHS.length; i++) {
    // "april 10" — digit must NOT be followed by more digits (avoids partial year match) or am/pm
    const afterMonth = lowerNoYear.match(new RegExp(`${MONTHS[i]}\\s+(\\d{1,2})(?!\\d)(?!\\s*[ap]m)`));
    if (afterMonth) {
      const mo = String(i + 1).padStart(2, '0');
      const dy = String(parseInt(afterMonth[1])).padStart(2, '0');
      return `${year}-${mo}-${dy}`;
    }
    // "10 april" — digit before month name, not preceded by more digits
    const beforeMonth = lowerNoYear.match(new RegExp(`(?<!\\d)(\\d{1,2})\\s+${MONTHS[i]}`));
    if (beforeMonth) {
      const mo = String(i + 1).padStart(2, '0');
      const dy = String(parseInt(beforeMonth[1])).padStart(2, '0');
      return `${year}-${mo}-${dy}`;
    }
  }

  return today.toISOString().slice(0, 10);
}

function parseDateRangeFromText(text: string): { start: string; end: string } {
  const lower = text.toLowerCase();
  const today = new Date();

  // "next week"
  if (lower.includes('next week')) {
    const monday = new Date(today);
    monday.setDate(today.getDate() + (7 - today.getDay() + 1) % 7 + 1);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { start: monday.toISOString().slice(0, 10), end: sunday.toISOString().slice(0, 10) };
  }

  // "this week"
  if (lower.includes('this week')) {
    const monday = new Date(today);
    monday.setDate(today.getDate() - today.getDay() + 1);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { start: monday.toISOString().slice(0, 10), end: sunday.toISOString().slice(0, 10) };
  }

  // "this month"
  if (lower.includes('this month')) {
    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
  }

  // "10-15 may" or "10 - 15 may" or "may 10-15" (day range within same month)
  for (let i = 0; i < MONTHS.length; i++) {
    const dashAfter = lower.match(new RegExp(`(\\d{1,2})\\s*[-–]\\s*(\\d{1,2})\\s+${MONTHS[i]}`));
    if (dashAfter) {
      const mo = String(i + 1).padStart(2, '0');
      const yr = today.getFullYear();
      return {
        start: `${yr}-${mo}-${String(parseInt(dashAfter[1])).padStart(2, '0')}`,
        end:   `${yr}-${mo}-${String(parseInt(dashAfter[2])).padStart(2, '0')}`,
      };
    }
    const dashBefore = lower.match(new RegExp(`${MONTHS[i]}\\s+(\\d{1,2})\\s*[-–]\\s*(\\d{1,2})`));
    if (dashBefore) {
      const mo = String(i + 1).padStart(2, '0');
      const yr = today.getFullYear();
      return {
        start: `${yr}-${mo}-${String(parseInt(dashBefore[1])).padStart(2, '0')}`,
        end:   `${yr}-${mo}-${String(parseInt(dashBefore[2])).padStart(2, '0')}`,
      };
    }
  }

  // "from X to Y" or "April 10 to April 15"
  const toMatch = text.match(/(?:from\s+)?(.+?)\s+(?:to|until|through)\s+(.+?)(?:\s|$)/i);
  if (toMatch) {
    const s = parseDateFromText(toMatch[1]);
    const e = parseDateFromText(toMatch[2]);
    if (s !== e) return { start: s, end: e };
  }

  const start = parseDateFromText(text);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return { start, end: end.toISOString().slice(0, 10) };
}

function extractHeadcount(text: string): number {
  const m = text.match(/(\d+)\s*(?:staff|workers?|people|persons?|nurses?|doctors?|shifts?)/i);
  if (m) return Math.min(parseInt(m[1]), 10);
  return 1;
}

function parseTimeRange(text: string): { start_time?: string; end_time?: string } {
  // matches "3am", "3:30am", "15:00", "3 am", etc.
  const timeRe = /(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/gi;
  const times: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = timeRe.exec(text)) !== null && times.length < 2) {
    let h = parseInt(m[1]);
    const min = m[2] ? parseInt(m[2]) : 0;
    const meridiem = m[3]?.toLowerCase();
    if (meridiem === 'pm' && h < 12) h += 12;
    if (meridiem === 'am' && h === 12) h = 0;
    times.push(`${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}:00`);
  }
  if (times.length === 2) return { start_time: times[0], end_time: times[1] };
  return {};
}

/** Extract a worker's full name from phrasing like "for Kavinda Silva" or "assign to John Doe". */
function extractWorkerName(text: string): string | null {
  // "for Kavinda Silva" — two or more capitalised words after "for"
  const forMatch = text.match(/\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/);
  if (forMatch) return forMatch[1];
  // "assign to John Doe" or "assign John Doe"
  const assignMatch = text.match(/\bassign(?:ed)?\s+(?:to\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/);
  if (assignMatch) return assignMatch[1];
  return null;
}

/** Returns true when the message is asking to create/add a single shift (not bulk-generate). */
function isSingleShiftRequest(text: string): boolean {
  const lower = text.toLowerCase();
  // Bulk-generation signals → not a single-shift request
  if (/\b(generate|roster)\b/.test(lower)) return false;
  if (/\b(next|this)\s+(week|month)\b/.test(lower)) return false;
  if (/\bfrom\b.+?\bto\b/.test(lower)) return false;
  // Single-creation verbs
  return /\b(create|add|assign|make|book|put)\b/.test(lower);
}

/** Score each shift type by how many of its name-words appear in the message text. */
function findBestShiftType(text: string, types: ShiftTypeItem[]): ShiftTypeItem | null {
  const lower = text.toLowerCase();
  let best: ShiftTypeItem | null = null;
  let bestScore = 0;
  for (const st of types) {
    const words = st.name.toLowerCase().split(/\s+/);
    const score = words.filter(w => w.length > 2 && lower.includes(w)).length;
    if (score > bestScore) { bestScore = score; best = st; }
  }
  return bestScore > 0 ? best : null;
}

function buildAssistantResponse(
  intent: string,
  routed_to: string,
  scheduleResult?: { filled: number; escalated: number; total_slots: number; reasoning_summary: string; slots?: ScheduleSlotResult[] },
): string {
  if (intent === 'schedule' && scheduleResult) {
    const { filled, escalated, total_slots, reasoning_summary, slots } = scheduleResult;

    let assignmentLines = '';
    if (slots && slots.length > 0) {
      assignmentLines = '\n**Assignments:**\n' + slots.map(s => {
        const worker = s.assigned_worker ?? '—';
        const status = s.status === 'escalated' ? ' ⚠️ escalated' : '';
        return `- **${s.shift_type}**: ${worker}${status}`;
      }).join('\n') + '\n';
    }

    return (
      `✅ **Schedule generated!**\n` +
      assignmentLines +
      `\n- **Slots processed:** ${total_slots}\n` +
      `- **Filled:** ${filled}\n` +
      `- **Escalated to manager:** ${escalated}\n\n` +
      `${reasoning_summary}\n\n` +
      (escalated > 0 ? `⚠️ ${escalated} slot(s) could not be filled automatically and were escalated.` : `All slots filled successfully.`)
    );
  }

  if (intent === 'swap') {
    const extra = (scheduleResult as unknown as { leaveId?: number; workerName?: string; leaveDate?: string } | undefined);
    if (extra?.leaveId) {
      return (
        `🔄 **Leave request created** (ID #${extra.leaveId})\n\n` +
        `- **Worker:** ${extra.workerName}\n` +
        `- **Date:** ${extra.leaveDate}\n\n` +
        `Open the **Swap Management** tab to review swap candidates and resolve.`
      );
    }
    return `🔄 **Swap request received.**\n\nThe swap agent has been notified. Please use the swap management panel to review candidates.`;
  }

  return (
    `ℹ️ **Intent detected:** \`${intent}\`\n\n` +
    `Routed to: \`${routed_to}\`\n\n` +
    `I can help you schedule shifts, find swap candidates, and manage your workforce. Try:\n` +
    `- "Generate ICU shifts for next week"\n` +
    `- "Schedule emergency shifts for April 10 to April 15"`
  );
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const { sbuCode, departmentCode, sessionId } = useAxis();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: trimmed };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    let responseText = '';

    try {
      if (!sbuCode || !departmentCode) {
        responseText = '⚠️ Please select an SBU and department from the top bar before scheduling.';
      } else {
        // Step 1: Route via orchestrator
        const routing = await orchestratorProcess(trimmed, sbuCode, sessionId);

        if (routing.intent === 'schedule') {
          const ep = routing.extracted_params as Record<string, unknown>;
          const { start: regexStart, end: regexEnd } = parseDateRangeFromText(trimmed);

          const dateStart = (ep.date_range_start as string) || regexStart;
          const dateEnd   = (ep.date_range_end   as string) || regexEnd;
          const epShiftType = ep.shift_type as string | null;

          // LLM extraction first, then regex fallback for worker name
          const workerName = (ep.worker_name as string | null) || extractWorkerName(trimmed);

          if (workerName || isSingleShiftRequest(trimmed)) {
            // ── Single-shift creation path ──
            const singleDate = (ep.date_range_start as string) || parseDateFromText(trimmed);
            const shiftTypes = await fetchShiftTypesList(sbuCode, departmentCode);

            if (shiftTypes.length === 0) {
              responseText = `⚠️ No shift types found for this department. Please check your SBU/department selection.`;
            } else {
              // Match shift type: prefer LLM-provided name, then score against message text
              const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
              const needle = normalize(epShiftType ?? '');
              const matched = needle
                ? (shiftTypes.find(st => normalize(st.name).includes(needle))
                    ?? shiftTypes.find(st => needle.includes(normalize(st.name))))
                : findBestShiftType(trimmed, shiftTypes);

              if (!matched) {
                const available = shiftTypes.map(s =>
                  `- **${s.name}** (${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)})`
                ).join('\n');
                responseText = `ℹ️ Which shift type would you like to create on **${singleDate}**?\n\n${available}`;
              } else {
                let workerId: number | null = null;
                let workerDisplayName = 'Open (unassigned)';
                let canProceed = true;

                if (workerName) {
                  const workers = await searchWorker(workerName, sbuCode);
                  if (workers.length === 0) {
                    responseText = `⚠️ Could not find a worker named **"${workerName}"**. Please check the name and try again.`;
                    canProceed = false;
                  } else {
                    const worker = workers[0];
                    workerId = worker.id;
                    workerDisplayName = worker.name;

                    // Pre-flight: worker already has a shift on this date?
                    const existingShifts = await fetchShifts(sbuCode, departmentCode, singleDate, singleDate);
                    const workerExisting = existingShifts.find(s => s.worker_id === worker.id);
                    if (workerExisting) {
                      responseText =
                        `⚠️ **${worker.name}** already has a shift on **${singleDate}**:\n\n` +
                        `- **${workerExisting.shift_type_name}** (${workerExisting.start_time.slice(0, 5)}–${workerExisting.end_time.slice(0, 5)}) \`[${workerExisting.status}]\`\n\n` +
                        `A worker cannot be assigned to more than one shift per day.`;
                      canProceed = false;
                    }
                  }
                }

                if (canProceed) {
                  try {
                    await createShiftManual({
                      worker_id: workerId,
                      shift_type_id: matched.id,
                      date: singleDate,
                      start_time: matched.start_time,
                      end_time: matched.end_time,
                      status: workerId ? 'confirmed' : 'open',
                    });
                    responseText =
                      `✅ **Shift created!**\n\n` +
                      `- **Shift:** ${matched.name}\n` +
                      `- **Date:** ${singleDate}\n` +
                      `- **Worker:** ${workerDisplayName}\n` +
                      `- **Time:** ${matched.start_time.slice(0, 5)}–${matched.end_time.slice(0, 5)}`;
                    queryClient.invalidateQueries({ queryKey: ['shifts'] });
                  } catch (err) {
                    const msg = err instanceof Error ? err.message : String(err);
                    const isConflict = msg.includes('409') || msg.toLowerCase().includes('conflict');
                    responseText = isConflict
                      ? `⚠️ **Schedule conflict:** ${msg.replace(/.*Conflict:\s*/i, '')}`
                      : `❌ **Failed to create shift:** ${msg}`;
                  }
                }
              }
            }
          } else {
            // ── Bulk schedule generation ──
            const regexTime = parseTimeRange(trimmed);
            const headcount = (ep.headcount as number) || extractHeadcount(trimmed);
            const startTime = (ep.start_time as string | null) || regexTime.start_time;
            const endTime   = (ep.end_time   as string | null) || regexTime.end_time;

            const constraints: Record<string, unknown> = {
              ...(ep.constraints as Record<string, unknown> | undefined),
              ...(startTime ? { start_time: startTime } : {}),
              ...(endTime   ? { end_time:   endTime   } : {}),
            };

            const result = await generateSchedule({
              sbu_code: sbuCode,
              department_code: departmentCode,
              date_range_start: dateStart,
              date_range_end: dateEnd,
              headcount_per_shift: headcount,
              session_id: sessionId,
              ...(Object.keys(constraints).length ? { constraints } : {}),
            });

            responseText = buildAssistantResponse('schedule', routing.routed_to, result);
            queryClient.invalidateQueries({ queryKey: ['shifts'] });
          }

        } else if (routing.intent === 'swap') {
          const ep = routing.extracted_params as Record<string, unknown>;
          const swapWorkerName = ep.worker_name as string | null;
          const leaveDate = (ep.leave_date as string | null) || parseDateFromText(trimmed);

          if (swapWorkerName && leaveDate) {
            // Search for the worker
            const workers = await searchWorker(swapWorkerName, sbuCode);
            if (workers.length === 0) {
              responseText = `⚠️ Could not find a worker named **"${swapWorkerName}"** in this SBU. Please check the name and try again.`;
            } else {
              const worker = workers[0];
              // Look for a shift on that date for this worker
              const shifts = await fetchShifts(sbuCode, departmentCode, leaveDate, leaveDate);
              const workerShift = shifts.find(s => s.worker_name === worker.name);
              const lr = await createLeaveRequest({
                worker_id: worker.id,
                shift_id: workerShift?.id,
                date: leaveDate,
                reason: trimmed,
              });
              responseText = buildAssistantResponse('swap', routing.routed_to, {
                leaveId: lr.id,
                workerName: worker.name,
                leaveDate,
              } as never);
              queryClient.invalidateQueries({ queryKey: ['leave-requests'] });
            }
          } else {
            responseText = `⚠️ I detected a swap/leave request but could not identify the worker name or date. Please be more specific, e.g. "Amara Perera is on leave on 5th May".`;
          }

        } else if (routing.intent === 'query') {
          // Prefer dates extracted by the LLM orchestrator; regex is only a fallback
          // when no LLM key is configured
          const ep = routing.extracted_params as Record<string, unknown>;
          const { start: regexStart, end: regexEnd } = parseDateRangeFromText(trimmed);
          const qStart = (ep.date_range_start as string) || regexStart;
          const qEnd   = (ep.date_range_end   as string) || regexEnd;
          const shifts = await fetchShifts(sbuCode, departmentCode, qStart, qEnd);
          if (shifts.length === 0) {
            responseText = `📋 No shifts found for **${qStart}**${qStart !== qEnd ? ` – **${qEnd}**` : ''} in this department.`;
          } else {
            const lines = shifts.map(s =>
              `- **${s.shift_type_name}** (${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}): ${s.worker_name || '—'} \`[${s.status}]\``
            );
            responseText =
              `📋 **Shifts for ${qStart}${qStart !== qEnd ? ` – ${qEnd}` : ''}:**\n\n` +
              lines.join('\n');
          }

        } else {
          responseText = buildAssistantResponse(routing.intent, routing.routed_to);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      responseText = `❌ **Error:** ${msg}\n\nMake sure the AXIS backend is running at \`${import.meta.env.VITE_API_URL ?? 'http://localhost:8001'}\`.`;
    }

    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), role: 'assistant', content: responseText },
    ]);
    setIsTyping(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-chat-bg border-r border-border">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/15">
          <Calendar className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="font-display font-semibold text-foreground text-sm">AXIS ShiftAI</h2>
          <p className="text-xs text-muted-foreground">Connected to AXIS backend</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 ${
              msg.role === 'user' ? 'bg-primary/20' : 'bg-secondary'
            }`}>
              {msg.role === 'user' ? (
                <User className="w-3.5 h-3.5 text-primary" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-muted-foreground" />
              )}
            </div>
            <div className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground'
            }`}>
              <ReactMarkdown
                components={{
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  ul: ({ children }) => <ul className="mt-1 space-y-0.5 list-disc list-inside">{children}</ul>,
                  p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                  code: ({ children }) => <code className="bg-black/10 rounded px-1 text-xs">{children}</code>,
                }}
              >
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 bg-secondary">
              <Bot className="w-3.5 h-3.5 text-muted-foreground" />
            </div>
            <div className="bg-secondary rounded-xl px-4 py-3">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2 bg-secondary rounded-xl px-4 py-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Schedule ICU shifts for next week…"
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground disabled:opacity-40 transition-opacity hover:opacity-90"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
