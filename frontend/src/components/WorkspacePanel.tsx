import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

/** Desktop landmark; focus-contained drawer only when the viewport calls for it. */
export default function WorkspacePanel({ children, modal, hidden, label, className, id }: {
  children: ReactNode; modal: boolean; hidden?: boolean; label: string; className: string; id: string;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!modal || hidden) return;
    const previous = document.activeElement as HTMLElement | null;
    const panel = ref.current!;
    const controls = () => [...panel.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, [tabindex="0"]')].filter(el => el.getClientRects().length > 0);
    (controls()[0] ?? panel).focus({ preventScroll: true });
    function trap(event: KeyboardEvent) {
      if (event.key !== 'Tab') return;
      const items = controls();
      const first = items[0] ?? panel, last = items.at(-1) ?? panel;
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) { event.preventDefault(); last.focus({ preventScroll: true }); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel)) { event.preventDefault(); first.focus({ preventScroll: true }); }
    }
    panel.addEventListener('keydown', trap);
    return () => { panel.removeEventListener('keydown', trap); previous?.focus({ preventScroll: true }); };
  }, [modal, hidden]);
  return <aside ref={ref} id={id} hidden={hidden} tabIndex={-1} className={className} aria-label={label} role={modal ? 'dialog' : undefined} aria-modal={modal || undefined}>{children}</aside>;
}
