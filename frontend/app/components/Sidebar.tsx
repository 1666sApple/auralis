'use client';

import Link from 'next/link';
import { Layers, Wand2 } from 'lucide-react';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();

  const navItems = [
    { name: 'Logo Overlay', path: '/', icon: Layers },
    { name: 'Prompt Enhancer', path: '/prompt-enhancer', icon: Wand2 },
  ];

  return (
    <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col h-full shrink-0">
      <div className="h-16 flex items-center px-6 border-b border-slate-700">
        <h1 className="font-bold text-lg text-white">CVM Tools</h1>
      </div>
      <div className="flex-1 py-4 flex flex-col gap-2 px-3">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link
              key={item.name}
              href={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  : 'text-slate-400 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium text-sm">{item.name}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
