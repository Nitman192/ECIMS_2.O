type MobileSidebarOverlayProps = {
  open: boolean;
  onClose: () => void;
};

export const MobileSidebarOverlay = ({ open, onClose }: MobileSidebarOverlayProps) => {
  return (
    <button
      type="button"
      tabIndex={open ? 0 : -1}
      aria-label="Close navigation"
      onClick={onClose}
      className={`fixed inset-0 z-30 bg-slate-950/45 backdrop-blur-sm transition lg:hidden ${
        open ? 'opacity-100' : 'pointer-events-none opacity-0'
      }`}
    />
  );
};
