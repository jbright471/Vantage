import {
  useEffect,
  useRef,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(",");

type OverlaySurfaceProps = {
  isOpen: boolean;
  onClose: () => void;
  labelledBy: string;
  describedBy?: string;
  variant?: "drawer" | "workspace";
  size?: "default" | "wide";
  className?: string;
  initialFocusRef?: RefObject<HTMLElement | null>;
  busy?: boolean;
  children: ReactNode;
};

type OverlayHeaderProps = {
  titleId: string;
  title: ReactNode;
  onClose: () => void;
  closeLabel: string;
  kicker?: ReactNode;
  description?: ReactNode;
  descriptionId?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  headingLevel?: 1 | 2 | 3;
  className?: string;
};

function getFocusableElements(surface: HTMLElement): HTMLElement[] {
  return Array.from(surface.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) => !element.hidden && element.getAttribute("aria-hidden") !== "true",
  );
}

export function OverlaySurface({
  isOpen,
  onClose,
  labelledBy,
  describedBy,
  variant = "drawer",
  size = "default",
  className,
  initialFocusRef,
  busy,
  children,
}: OverlaySurfaceProps) {
  const surfaceRef = useRef<HTMLElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const backdropPointerStartedRef = useRef(false);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusTarget =
      initialFocusRef?.current ??
      surfaceRef.current?.querySelector<HTMLElement>("[data-overlay-autofocus]") ??
      (surfaceRef.current ? getFocusableElements(surfaceRef.current)[0] : null) ??
      surfaceRef.current;
    focusTarget?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      const surface = surfaceRef.current;
      if (!surface) {
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusableElements = getFocusableElements(surface);
      if (focusableElements.length === 0) {
        event.preventDefault();
        surface.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      if (event.shiftKey && (document.activeElement === firstElement || document.activeElement === surface)) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousBodyOverflow;
      const restoreTarget = restoreFocusRef.current;
      if (restoreTarget && document.contains(restoreTarget)) {
        restoreTarget.focus();
      }
    };
  }, [initialFocusRef, isOpen]);

  if (!isOpen) {
    return null;
  }

  const surfaceClassName = [
    "overlay-surface",
    `is-${variant}`,
    `is-${size}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return createPortal(
    <div
      className={`overlay-backdrop is-${variant}`}
      role="presentation"
      onPointerDown={(event) => {
        backdropPointerStartedRef.current = event.target === event.currentTarget;
      }}
      onPointerUp={(event) => {
        const shouldClose = backdropPointerStartedRef.current && event.target === event.currentTarget;
        backdropPointerStartedRef.current = false;
        if (shouldClose) {
          onCloseRef.current();
        }
      }}
      onPointerCancel={() => {
        backdropPointerStartedRef.current = false;
      }}
    >
      <aside
        ref={surfaceRef}
        className={surfaceClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        aria-busy={busy || undefined}
        tabIndex={-1}
      >
        {children}
      </aside>
    </div>,
    document.body,
  );
}

export function OverlayHeader({
  titleId,
  title,
  onClose,
  closeLabel,
  kicker,
  description,
  descriptionId,
  meta,
  actions,
  headingLevel = 2,
  className,
}: OverlayHeaderProps) {
  const Heading = `h${headingLevel}` as const;

  return (
    <header className={["overlay-header", className].filter(Boolean).join(" ")}>
      <div className="overlay-header-copy">
        {kicker ? <p className="section-kicker">{kicker}</p> : null}
        <Heading id={titleId}>{title}</Heading>
        {meta ? <p className="overlay-meta">{meta}</p> : null}
        {description ? (
          <p id={descriptionId} className="overlay-description">
            {description}
          </p>
        ) : null}
      </div>
      <div className="overlay-header-actions">
        {actions}
        <button type="button" className="overlay-close-button" aria-label={closeLabel} onClick={onClose}>
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </header>
  );
}
