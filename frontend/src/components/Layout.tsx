import { useEffect, useState } from "react";
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { Shield, Home, ClipboardList, History, LogOut, Bell, User, FolderLock, ShieldAlert, BarChart3, FlaskConical, Cpu, Camera, Activity, ShieldCheck, Building2, Sliders, Archive, Server } from 'lucide-react';
import { getNotifications } from '../services/reviewApi';
import type { NotificationItem } from '../types/review';

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const notifs = await getNotifications(5);
        setNotifications(notifs);
        setUnreadCount(notifs.filter(n => !n.is_read).length);
      } catch (error) {
        console.error('Failed to fetch notifications', error);
      }
    };
    
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('sentinex_token');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-[#f4f6f9] overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1a2332] text-gray-300 flex flex-col flex-shrink-0 shadow-xl z-20">
        <div className="h-16 flex items-center px-6 border-b border-gray-700 bg-[#151c28]">
          <Shield className="w-6 h-6 text-blue-500 mr-2" />
          <span className="text-white font-bold tracking-widest">SENTINEX</span>
        </div>
        <div className="px-6 py-3 border-b border-gray-800 bg-[#1c2636]">
          <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider block">Enterprise Platform</span>
          <span className="text-sm font-medium text-gray-400 leading-tight block mt-0.5">Alerts, Audit &amp; Analytics</span>
        </div>

        <nav className="flex-1 py-3 space-y-1 overflow-y-auto px-3">
          <div className="px-3 pt-1 pb-1 text-[11px] font-bold text-gray-500 uppercase tracking-wider">Operations</div>
          {[
            { path: '/live-camera', label: 'Live Camera Demo', icon: Camera },
            { path: '/review', label: 'Review Dashboard', icon: Home },
            { path: '/alerts', label: 'Alert Center', icon: Bell },
            { path: '/evidence', label: 'Evidence Vault', icon: FolderLock },
            { path: '/audit', label: 'Audit Trail', icon: ShieldAlert },
            { path: '/tasks', label: 'Investigation Tasks', icon: ClipboardList },
            { path: '/history', label: 'Review History', icon: History },
          ].map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive || location.pathname.startsWith(`${item.path}/`)
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-4 h-4 mr-3 flex-shrink-0" />
              {item.label}
            </NavLink>
          ))}

          <div className="px-3 pt-3 pb-1 text-[11px] font-bold text-gray-500 uppercase tracking-wider">Module 11 Analytics</div>
          {[
            { path: '/analytics', label: 'System Analytics', icon: BarChart3 },
            { path: '/analytics/evaluation', label: 'AI Evaluation Engine', icon: FlaskConical },
            { path: '/analytics/models', label: 'Model & Drift Monitor', icon: Cpu },
            { path: '/analytics/cameras', label: 'Camera Analytics', icon: Camera },
            { path: '/analytics/health', label: 'System Health', icon: Activity },
          ].map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/analytics'}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-4 h-4 mr-3 flex-shrink-0" />
              {item.label}
            </NavLink>
          ))}

          <div className="px-3 pt-3 pb-1 text-[11px] font-bold text-blue-400 uppercase tracking-wider">Module 12 Admin</div>
          {[
            { path: '/admin', label: 'Control Center', icon: ShieldCheck, exact: true },
            { path: '/admin/users', label: 'User Directory', icon: User },
            { path: '/admin/departments', label: 'Departments', icon: Building2 },
            { path: '/admin/cameras', label: 'CCTV Feeds', icon: Camera },
            { path: '/admin/config', label: 'System Config', icon: Sliders },
            { path: '/admin/workers', label: 'Worker Fleet', icon: Server },
            { path: '/admin/backups', label: 'Backups Vault', icon: Archive },
            { path: '/admin/audit', label: 'System Audit', icon: ShieldAlert },
          ].map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-4 h-4 mr-3 flex-shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-800">
          <button
            onClick={handleLogout}
            className="flex items-center w-full px-3 py-2 text-sm font-medium text-red-400 rounded-md hover:bg-gray-800 hover:text-red-300 transition-colors"
          >
            <LogOut className="w-4 h-4 mr-3" />
            Secure Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-gray-200 shadow-sm flex items-center justify-between px-6 z-10 flex-shrink-0">
          <div className="text-sm text-gray-500 font-medium">
            {location.pathname === '/live-camera' ? 'Live Camera Demo / Laptop Front Camera' :
             location.pathname.includes('/review/') ? 'Review Queue / Event Details' : 
             location.pathname === '/review' ? 'Dashboard / Overview' :
             location.pathname === '/tasks' ? 'Tasks / Active Cases' :
             location.pathname === '/history' ? 'Audit / History' :
             location.pathname === '/analytics' ? 'OMYRA — System Analytics' :
             location.pathname === '/analytics/evaluation' ? 'AI Evaluation & Research Dashboard' :
             location.pathname === '/analytics/models' ? 'Model Registry & Drift Monitoring' :
             location.pathname === '/analytics/cameras' ? 'Camera Processing & Quality Analytics' :
             location.pathname === '/analytics/health' ? 'System Infrastructure Health' : ''}
          </div>
          
          <div className="flex items-center gap-6">
            <div className="relative cursor-pointer">
              <Bell className="w-5 h-5 text-gray-500 hover:text-gray-700" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center border-2 border-white">
                  {unreadCount}
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-2 border-l border-gray-200 pl-6">
              <div className="bg-gray-100 p-1.5 rounded-full">
                <User className="w-5 h-5 text-gray-600" />
              </div>
              <div className="text-sm">
                <div className="font-medium text-gray-700 leading-tight">Authorized Officer</div>
                <div className="text-xs text-green-600 font-medium flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 inline-block"></span> Active Session
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 scroll-smooth">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
