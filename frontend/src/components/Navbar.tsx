"use client";

import Image from 'next/image'
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import logo from '@/../public/logo.png';

export default function Navbar() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Image src={logo} alt="Cloud Manager Logo" width={32} height={32} className="rounded-lg" />
          <span className="font-semibold text-lg">Cloud Manager</span>
        </div>

        {user && (
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{user.username}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
