export type ShiftRole = 'nurse' | 'doctor' | 'tech' | 'admin';

export interface Shift {
  id: string;
  title: string;
  start: Date;
  end: Date;
  role: ShiftRole;
  employee?: string;
  notes?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  shifts?: Shift[];
}
