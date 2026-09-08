import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { OverlayHeader, OverlaySurface } from "../../components/OverlaySurface";
import { parseOperatorGuide, type ParsedGuide } from "./operatorGuide";


const OPERATOR_GUIDE_URL = "/api/docs/operator-guide.md";

function docsHref(slug: string): string {
  const url = new URL(window.location.href);
  url.searchParams.set("docs", slug);
  return `${url.pathname}${url.search}${url.hash}`;
}

type GuideStatus = "loading" | "ready" | "error";

type OperatorGuideDrawerProps = {
  isOpen: boolean;
  selectedSlug: string | null;
  onClose: () => void;
  onNavigate: (slug: string, options?: { replace?: boolean }) => void;
};

export function OperatorGuideDrawer({
  isOpen,
  selectedSlug,
  onClose,
  onNavigate,
}: OperatorGuideDrawerProps) {
  const [guide, setGuide] = useState<ParsedGuide | null>(null);
  const [status, setStatus] = useState<GuideStatus>("loading");
  const [searchQuery, setSearchQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const contentPanelRef = useRef<HTMLDivElement>(null);
  const pageHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousPageSlugRef = useRef<string | null>(null);

  const selectedPage = guide?.pages.find((page) => page.slug === selectedSlug) ?? guide?.pages[0] ?? null;
  const selectedPageIndex = selectedPage && guide ? guide.pages.indexOf(selectedPage) : -1;
  const previousPage = guide && selectedPageIndex > 0 ? guide.pages[selectedPageIndex - 1] : null;
  const nextPage = guide && selectedPageIndex >= 0 ? guide.pages[selectedPageIndex + 1] ?? null : null;

  const filteredGroups = useMemo(() => {
    if (!guide) {
      return [];
    }

    const queryTerms = searchQuery.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (queryTerms.length === 0) {
      return guide.groups;
    }

    return guide.groups
      .map((group) => ({
        ...group,
        pages: group.pages.filter((page) => {
          const compactSearchText = page.searchText.replace(/\s+/g, "");
          return queryTerms.every(
            (term) => page.searchText.includes(term) || compactSearchText.includes(term.replace(/\s+/g, "")),
          );
        }),
      }))
      .filter((group) => group.pages.length > 0);
  }, [guide, searchQuery]);

  const filteredPageCount = filteredGroups.reduce((count, group) => count + group.pages.length, 0);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let isMounted = true;

    async function loadOperatorGuide() {
      setGuide(null);
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
        const parsedGuide = parseOperatorGuide(markdown);
        if (parsedGuide.pages.length === 0) {
          throw new Error("Operator guide does not contain any readable sections");
        }

        if (isMounted) {
          setGuide(parsedGuide);
          setStatus("ready");
        }
      } catch (error) {
        console.error(error);

        if (isMounted) {
          setStatus("error");
        }
      }
    }

    void loadOperatorGuide();

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  useEffect(() => {
    if (status === "ready") {
      searchRef.current?.focus();
    }
  }, [status]);

  useEffect(() => {
    if (status !== "ready" || !selectedPage) {
      return;
    }

    if (selectedSlug !== selectedPage.slug) {
      onNavigate(selectedPage.slug, { replace: true });
    }
  }, [onNavigate, selectedPage, selectedSlug, status]);

  useEffect(() => {
    if (!selectedPage) {
      return;
    }

    const previousSlug = previousPageSlugRef.current;
    previousPageSlugRef.current = selectedPage.slug;
    if (!previousSlug || previousSlug === selectedPage.slug) {
      return;
    }

    if (contentPanelRef.current) {
      contentPanelRef.current.scrollTop = 0;
    }
    pageHeadingRef.current?.focus();
  }, [selectedPage]);

  if (!isOpen) {
    return null;
  }

  return (
    <OverlaySurface
      isOpen={isOpen}
      onClose={onClose}
      labelledBy="docs-drawer-title"
      describedBy="docs-drawer-description"
      variant="workspace"
      className={`docs-drawer is-${status}`}
      busy={status === "loading"}
    >
      <OverlayHeader
        titleId="docs-drawer-title"
        title="Operator Guide"
        kicker="Docs / Control_Plane"
        description="Focused operating guidance, loaded live from the repository."
        descriptionId="docs-drawer-description"
        closeLabel="Close operator guide"
        onClose={onClose}
        headingLevel={1}
        className="docs-workspace-header"
        actions={
          <a className="ghost-link" href={OPERATOR_GUIDE_URL} target="_blank" rel="noreferrer">
            Open Markdown
          </a>
        }
      />

      <div className="docs-workspace">
          <aside className="docs-sidebar" aria-label="Guide navigation">
            <div className="docs-search-block">
              <label htmlFor="docs-search">Search guide</label>
              <input
                ref={searchRef}
                id="docs-search"
                type="search"
                name="docs-search"
                value={searchQuery}
                placeholder="Search sections and content…"
                autoComplete="off"
                spellCheck={false}
                disabled={status !== "ready"}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              <p aria-live="polite">
                {status === "ready"
                  ? `${filteredPageCount} ${filteredPageCount === 1 ? "section" : "sections"}`
                  : "Loading sections…"}
              </p>
            </div>

            {status === "ready" ? (
              filteredGroups.length > 0 ? (
                <nav className="docs-section-nav" aria-label="Operator guide sections">
                  {filteredGroups.map((group) => (
                    <section className="docs-nav-group" key={group.slug} aria-labelledby={`docs-group-${group.slug}`}>
                      <h3 id={`docs-group-${group.slug}`}>{group.title}</h3>
                      <div className="docs-nav-items">
                        {group.pages.map((page) => (
                          <a
                            href={docsHref(page.slug)}
                            className={page.slug === selectedPage?.slug ? "is-active" : undefined}
                            aria-current={page.slug === selectedPage?.slug ? "page" : undefined}
                            key={page.slug}
                            onClick={(event) => {
                              if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                                return;
                              }
                              event.preventDefault();
                              setSearchQuery("");
                              onNavigate(page.slug);
                            }}
                          >
                            <span aria-hidden="true" className="docs-nav-marker" />
                            <span>{page.title}</span>
                          </a>
                        ))}
                      </div>
                    </section>
                  ))}
                </nav>
              ) : (
                <div className="docs-empty-state">
                  <strong>No matching sections</strong>
                  <p>Try a broader term, such as node, eval, token, or backup.</p>
                  <button type="button" className="text-action-button" onClick={() => setSearchQuery("")}>
                    Clear search
                  </button>
                </div>
              )
            ) : null}
          </aside>

          <div ref={contentPanelRef} className="docs-content-panel">
            {status === "loading" ? (
              <div className="docs-status-panel" role="status">
                <span className="docs-loading-indicator" aria-hidden="true" />
                <h2>Loading operator guide</h2>
                <p>Reading the live documentation from Vantage.</p>
              </div>
            ) : null}

            {status === "error" ? (
              <div className="docs-status-panel" role="alert">
                <p className="section-kicker">Docs unavailable</p>
                <h2>Guide unavailable</h2>
                <p>
                  Vantage could not load <code>OPERATOR_GUIDE.md</code>. Confirm the backend is running and the guide
                  exists at the repository root.
                </p>
              </div>
            ) : null}

            {status === "ready" && guide && selectedPage ? (
              <div className="docs-page">
                <nav className="docs-breadcrumbs" aria-label="Breadcrumb">
                  <span>{guide.title}</span>
                  <span aria-hidden="true">/</span>
                  <span>{selectedPage.groupTitle}</span>
                  <span aria-hidden="true">/</span>
                  <span aria-current="page">{selectedPage.title}</span>
                </nav>

                <header className="docs-page-header">
                  <p className="section-kicker">{selectedPage.groupTitle}</p>
                  <h2 ref={pageHeadingRef} tabIndex={-1}>
                    {selectedPage.title}
                  </h2>
                  <p>
                    Section {selectedPageIndex + 1} of {guide.pages.length}
                  </p>
                </header>

                <article className="markdown-body docs-markdown-body">
                  {selectedPage.markdown ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedPage.markdown}</ReactMarkdown>
                  ) : (
                    <p>No additional guidance is available for this section yet.</p>
                  )}
                </article>

                <nav className="docs-page-pagination" aria-label="Guide pagination">
                  {previousPage ? (
                    <a
                      href={docsHref(previousPage.slug)}
                      onClick={(event) => {
                        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                          return;
                        }
                        event.preventDefault();
                        onNavigate(previousPage.slug);
                      }}
                    >
                      <span>Previous</span>
                      <strong>{previousPage.title}</strong>
                    </a>
                  ) : (
                    <span />
                  )}
                  {nextPage ? (
                    <a
                      href={docsHref(nextPage.slug)}
                      className="is-next"
                      onClick={(event) => {
                        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                          return;
                        }
                        event.preventDefault();
                        onNavigate(nextPage.slug);
                      }}
                    >
                      <span>Next</span>
                      <strong>{nextPage.title}</strong>
                    </a>
                  ) : (
                    <span />
                  )}
                </nav>
              </div>
            ) : null}
          </div>
      </div>
    </OverlaySurface>
  );
}
