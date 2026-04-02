import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar } from 'lucide-react';
import { ChatMessage, Shift } from '@/types/shift';
import { parseShiftsFromMessage, generateAgentResponse } from '@/lib/shift-parser';
import ReactMarkdown from 'react-markdown';

interface ChatPanelProps {
  onShiftsCreated: (shifts: Shift[]) => void;
}

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: `👋 **Welcome to ShiftAI!**\n\nI'm your scheduling assistant. Tell me about the shifts you need and I'll add them to your calendar.\n\n**Try saying:**\n- "Schedule a nurse shift tomorrow 7am to 3pm"\n- "Add 3 doctor shifts on Monday 9am-5pm"\n- "Create an evening tech shift for Friday assigned to Sarah"\n- "I need 2 admin shifts on 4/15 from 8am to 4pm"`,
};

export function ChatPanel({ onShiftsCreated }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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

    // Simulate agent "thinking"
    await new Promise(r => setTimeout(r, 800 + Math.random() * 700));

    const shifts = parseShiftsFromMessage(trimmed);
    const responseText = generateAgentResponse(trimmed, shifts);

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: responseText,
      shifts,
    };

    setMessages(prev => [...prev, assistantMsg]);
    setIsTyping(false);

    if (shifts.length > 0) {
      onShiftsCreated(shifts);
    }
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
          <h2 className="font-display font-semibold text-foreground text-sm">ShiftAI Assistant</h2>
          <p className="text-xs text-muted-foreground">Describe your shifts naturally</p>
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
            placeholder="Describe the shift you need..."
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
