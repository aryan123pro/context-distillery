import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import EngineConsole from "@/components/EngineConsole";
import { Toaster } from "@/components/ui/toaster";

export default function App() {
  return (
    <div data-testid="app-root">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<EngineConsole />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}
