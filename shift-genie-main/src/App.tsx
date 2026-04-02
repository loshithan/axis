import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AxisProvider } from "@/context/AxisContext";
import { Sidebar } from "@/components/Sidebar";
import { ContextBar } from "@/components/ContextBar";
import Index from "./pages/Index.tsx";
import { EmployeesPage } from "./pages/EmployeesPage.tsx";
import { PayrollPage } from "./pages/PayrollPage.tsx";
import { TimesheetPage } from "./pages/TimesheetPage.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AxisProvider>
          <div className="flex flex-col h-screen overflow-hidden bg-background">
            {/* Top bar */}
            <ContextBar />
            {/* Body */}
            <div className="flex flex-1 min-h-0">
              <Sidebar />
              <main className="flex-1 min-w-0 overflow-hidden">
                <Routes>
                  <Route path="/"           element={<Index />} />
                  <Route path="/employees"  element={<EmployeesPage />} />
                  <Route path="/payroll"    element={<PayrollPage />} />
                  <Route path="/timesheet"  element={<TimesheetPage />} />
                  <Route path="*"           element={<NotFound />} />
                </Routes>
              </main>
            </div>
          </div>
        </AxisProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
