import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import ReviewDashboard from './pages/ReviewDashboard';
import ReviewDetails from './pages/ReviewDetails';
import InvestigationTasks from './pages/InvestigationTasks';
import ReviewHistory from './pages/ReviewHistory';
import AlertDashboard from './pages/AlertDashboard';
import AlertDetails from './pages/AlertDetails';
import NotificationHistory from './pages/NotificationHistory';
import EvidenceDashboard from './pages/EvidenceDashboard';
import EvidenceDetails from './pages/EvidenceDetails';
import EvidenceTimelinePage from './pages/EvidenceTimeline';
import AuditDashboard from './pages/AuditDashboard';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import EvaluationDashboard from './pages/EvaluationDashboard';
import ModelMonitoring from './pages/ModelMonitoring';
import CameraAnalytics from './pages/CameraAnalytics';
import SystemHealth from './pages/SystemHealth';
import AdminDashboard from './pages/AdminDashboard';
import AdminUserManagement from './pages/AdminUserManagement';
import AdminDepartmentManagement from './pages/AdminDepartmentManagement';
import AdminCameraManagement from './pages/AdminCameraManagement';
import AdminSystemConfig from './pages/AdminSystemConfig';
import AdminWorkerMonitor from './pages/AdminWorkerMonitor';
import AdminBackupManagement from './pages/AdminBackupManagement';
import AdminAuditLogs from './pages/AdminAuditLogs';
import LiveCameraDemo from './pages/LiveCameraDemo';
import Layout from './components/Layout';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('sentinex_token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Navigate to="/review" replace />} />
          <Route path="review" element={<ReviewDashboard />} />
          <Route path="review/:eventId" element={<ReviewDetails />} />
          <Route path="alerts" element={<AlertDashboard />} />
          <Route path="alerts/:alertId" element={<AlertDetails />} />
          <Route path="notifications" element={<NotificationHistory />} />
          <Route path="tasks" element={<InvestigationTasks />} />
          <Route path="history" element={<ReviewHistory />} />
          <Route path="evidence" element={<EvidenceDashboard />} />
          <Route path="evidence/:evidenceId" element={<EvidenceDetails />} />
          <Route path="evidence/:evidenceId/timeline" element={<EvidenceTimelinePage />} />
          <Route path="audit" element={<AuditDashboard />} />
          <Route path="analytics" element={<AnalyticsDashboard />} />
          <Route path="analytics/evaluation" element={<EvaluationDashboard />} />
          <Route path="analytics/models" element={<ModelMonitoring />} />
          <Route path="analytics/cameras" element={<CameraAnalytics />} />
          <Route path="analytics/health" element={<SystemHealth />} />
          <Route path="live-camera" element={<LiveCameraDemo />} />

          {/* Module 12: Admin & System Management */}
          <Route path="admin" element={<AdminDashboard />} />
          <Route path="admin/users" element={<AdminUserManagement />} />
          <Route path="admin/departments" element={<AdminDepartmentManagement />} />
          <Route path="admin/cameras" element={<AdminCameraManagement />} />
          <Route path="admin/cameras/demo" element={<LiveCameraDemo />} />
          <Route path="admin/config" element={<AdminSystemConfig />} />
          <Route path="admin/workers" element={<AdminWorkerMonitor />} />
          <Route path="admin/backups" element={<AdminBackupManagement />} />
          <Route path="admin/audit" element={<AdminAuditLogs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
