import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


const OPERATOR_GUIDE_URL = "/api/docs/operator-guide.md";

type GuideStatus = "loading" | "ready" | "error";

type OperatorGuideDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function OperatorGuideDrawer({ isOpen, onClose }: OperatorGuideDrawerProps) {
  const [content, setContent] = useState("Loading documentation...");
  const [status, setStatus] = useState<GuideStatus>("loading");

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let isMounted = true;

    async function loadOperatorGuide() {
      setContent("Loading documentation...");
      setStatus("loading");

      try {
        const response = await fetch(OPERATOR_GUIDE_URL, {
          headers: {
            Accept: "text/markdown",
          },
        });

        if (!response.ok) {
          throw new Error(`Operator guide request failed with ${response.status}`);
        }

        const markdown = await response.text();

        if (isMounted) {
          setContent(markdown);
          setStatus("ready");
        }
      } catch (error) {
        console.error(error);

        if (isMounted) {
          setContent(
            "### Guide unavailable\n\nVantage could not load `OPERATOR_GUIDE.md`. Confirm the backend is running and the guide exists at the repository root.",
          );
          setStatus("error");
        }
      }
    }

    void loadOperatorGuide();

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="run-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className={`run-drawer docs-drawer is-${status}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="docs-drawer-title"
        aria-busy={status === "loading"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <div>
            <p className="section-kicker">Docs</p>
            <h3 id="docs-drawer-title">Operator Guide</h3>
            <p className="drawer-run-id">Live markdown from {OPERATOR_GUIDE_URL}</p>
          </div>
          <button type="button" className="drawer-close-button" aria-label="Close operator guide" onClick={onClose}>
            X
          </button>
        </header>

        <div className="drawer-content docs-drawer-content">
          <div className="docs-actions">
            <a className="ghost-link" href={OPERATOR_GUIDE_URL} target="_blank" rel="noreferrer">
              Open raw markdown
            </a>
          </div>

          {status === "loading" ? <p className="docs-loading">Loading operator documentation...</p> : null}

          <article className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </article>
        </div>
      </aside>
    </div>
  );
}
