"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Home, LibraryBig, Map, User } from "lucide-react";

type MobileNavItem = {
  label: string;
  href: string;
  icon: React.ElementType;
  matchPrefix?: string;
};

const MOBILE_NAV_ITEMS: MobileNavItem[] = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "Trails", href: "/trails", icon: Map, matchPrefix: "/trails" },
  { label: "Explore", href: "/explore", icon: Compass },
  { label: "Quizzes", href: "/quizzes", icon: LibraryBig },
  { label: "Profile", href: "/settings", icon: User },
];

export default function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex h-[calc(4rem+env(safe-area-inset-bottom))] items-center border-t border-slate-200 bg-white px-1 pb-[env(safe-area-inset-bottom)]">
      {MOBILE_NAV_ITEMS.map((item) => {
        const isActive = item.matchPrefix
          ? pathname.startsWith(item.matchPrefix)
          : pathname === item.href;
        const Icon = item.icon;
        return (
          <Link
            key={item.label}
            href={item.href}
            className={`flex flex-1 flex-col items-center gap-0.5 rounded-lg py-2 text-center transition-colors ${
              isActive ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className="text-[10px] font-medium">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
