import { useEffect, useRef, useState } from 'react';
import { FiChevronDown, FiLogOut, FiUser } from 'react-icons/fi';

type UserDropdownProps = {
  userName: string;
  userRole: string;
  onLogout: () => void;
};

export const UserDropdown = ({ userName, userRole, onLogout }: UserDropdownProps) => {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!wrapperRef.current) return;
      if (event.target instanceof Node && !wrapperRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-left text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-slate-900 text-xs text-white dark:bg-slate-100 dark:text-slate-900">
          <FiUser />
        </span>
        <span className="hidden sm:block">
          <span className="block max-w-28 truncate text-sm font-medium">{userName}</span>
        </span>
        <FiChevronDown className={`text-sm transition ${open ? 'rotate-180' : ''}`} />
      </button>

      <div
        className={`absolute right-0 z-40 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/10 transition dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40 ${
          open ? 'translate-y-0 opacity-100' : 'pointer-events-none -translate-y-1 opacity-0'
        }`}
      >
        <div className="rounded-lg border border-slate-200/80 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
          <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{userName}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{userRole}</p>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40"
        >
          <FiLogOut />
          Sign out
        </button>
      </div>
    </div>
  );
};
