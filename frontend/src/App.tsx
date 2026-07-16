import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/auth/LoginPage';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import TicketsPage from './pages/TicketsPage';
import AlertsPage from './pages/AlertsPage';
import CustomersPage from './pages/CustomersPage';
import OSPatchesPage from './pages/OSPatchesPage';
import ScriptsPage from './pages/ScriptsPage';
import AutomationPage from './pages/AutomationPage';
import ReportsPage from './pages/ReportsPage';
import BillingPage from './pages/BillingPage';
import AdminPage from './pages/AdminPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="patches" element={<OSPatchesPage />} />
          <Route path="scripts" element={<ScriptsPage />} />
          <Route path="automation" element={<AutomationPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="billing" element={<BillingPage />} />
          <Route path="admin" element={<AdminPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}
