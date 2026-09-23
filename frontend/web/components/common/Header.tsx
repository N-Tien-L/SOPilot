'use client';

import { useState } from 'react';
import { useAuthStore } from '@/store/auth-store';
import { UserRole } from '@/interfaces/enums/core/user-role.enum';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  const { user } = useAuthStore();
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const roleLabels: Record<UserRole, string> = {
    [UserRole.USER]: 'Người dùng',
    [UserRole.MANAGER]: 'Quản lý',
    [UserRole.ADMIN]: 'Quản trị viên',
  };

  const roleColors: Record<UserRole, string> = {
    [UserRole.USER]: 'bg-blue-500/20 text-blue-400',
    [UserRole.MANAGER]: 'bg-emerald-500/20 text-emerald-400',
    [UserRole.ADMIN]: 'bg-purple-500/20 text-purple-400',
  };

  return (
    <header className="mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{title}</h1>
          {subtitle && <p className="text-slate-400 mt-1">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-4">
          {/* Role Badge */}
          {user?.role && (
            <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${roleColors[user.role]}`}>
              {roleLabels[user.role]}
            </span>
          )}

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 rounded-xl bg-slate-800/50 hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-slate-800/95 backdrop-blur-xl rounded-xl border border-slate-700/50 shadow-2xl z-50">
                <div className="p-4 border-b border-slate-700/50">
                  <h3 className="font-semibold text-white">Thông báo</h3>
                </div>
                <div className="p-4">
                  <p className="text-slate-400 text-sm text-center">Không có thông báo mới</p>
                </div>
              </div>
            )}
          </div>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-800/50 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-white font-semibold">
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="text-left">
                <p className="text-sm font-medium text-white">{user?.username || 'User'}</p>
                <p className="text-xs text-slate-400">{user?.email || 'user@poliwise.com'}</p>
              </div>
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-slate-800/95 backdrop-blur-xl rounded-xl border border-slate-700/50 shadow-2xl z-50">
                <div className="p-4 border-b border-slate-700/50">
                  <p className="font-medium text-white">{user?.username}</p>
                  <p className="text-sm text-slate-400">{user?.email}</p>
                </div>
                <div className="p-2">
                  <a href="/profile" className="flex items-center gap-3 px-3 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700/50 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    Hồ sơ cá nhân
                  </a>
                  <a href="/settings" className="flex items-center gap-3 px-3 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700/50 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Cài đặt
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
