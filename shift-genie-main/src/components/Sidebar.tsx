import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { CalendarDays, Users, DollarSign, Clock, Zap, Menu, X } from 'lucide-react';

const NAV_ITEMS = [
  { to: '/',          icon: CalendarDays, label: 'Scheduling' },
  { to: '/employees', icon: Users,        label: 'Employees'  },
  { to: '/timesheet', icon: Clock,        label: 'Time Sheet' },
  { to: '/payroll',   icon: DollarSign,   label: 'Payroll'    },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={`flex flex-col flex-shrink-0 h-full bg-card border-r border-border transition-all duration-300 ${
        collapsed ? 'w-[56px]' : 'w-[200px]'
      }`}
    >
      {/* Logo + burger */}
      <div className={`flex items-center border-b border-border h-[49px] px-3 ${collapsed ? 'justify-center' : 'justify-between'}`}>
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/20 flex-shrink-0">
              <Zap className="w-3.5 h-3.5 text-primary" />
            </div>
            <div>
              <div className="font-display font-bold text-foreground text-sm leading-tight">AXIS</div>
              <div className="text-[10px] text-muted-foreground leading-tight">Workforce AI</div>
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(v => !v)}
          className="flex items-center justify-center w-8 h-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors flex-shrink-0"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <Menu className="w-4 h-4" /> : <X className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                collapsed ? 'justify-center' : ''
              } ${
                isActive
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-border">
          <div className="text-[10px] text-muted-foreground">v0.1.0 · Hemas</div>
        </div>
      )}
    </div>
  );
}
