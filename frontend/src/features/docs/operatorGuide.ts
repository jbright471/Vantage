export type GuidePage = {
  slug: string;
  title: string;
  groupTitle: string;
  markdown: string;
  searchText: string;
};

export type GuideGroup = {
  slug: string;
  title: string;
  pages: GuidePage[];
};

export type ParsedGuide = {
  title: string;
  groups: GuideGroup[];
  pages: GuidePage[];
};

type PageDraft = {
  title: string;
  lines: string[];
};

type GroupDraft = {
  title: string;
  preface: string[];
  pages: PageDraft[];
};

function compactMarkdown(lines: string[]): string {
  return lines.join("\n").trim();
}

function searchableText(markdown: string): string {
  return markdown
    .replace(/^\s*(?:```|~~~).*$/gm, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[#>*|~]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function createSlug(value: string, usedSlugs: Map<string, number>): string {
  const baseSlug =
    value
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "section";
  const nextCount = (usedSlugs.get(baseSlug) ?? 0) + 1;
  usedSlugs.set(baseSlug, nextCount);
  return nextCount === 1 ? baseSlug : `${baseSlug}-${nextCount}`;
}

function trimHeading(value: string): string {
  return value.replace(/\s+#+\s*$/, "").trim();
}

export function parseOperatorGuide(markdown: string): ParsedGuide {
  const intro: string[] = [];
  const groupDrafts: GroupDraft[] = [];
  let guideTitle = "Vantage Operator Guide";
  let activeGroup: GroupDraft | null = null;
  let activePage: PageDraft | null = null;
  let fenceMarker: "`" | "~" | null = null;

  function finishPage() {
    if (activeGroup && activePage) {
      activeGroup.pages.push(activePage);
    }
    activePage = null;
  }

  function finishGroup() {
    finishPage();
    if (!activeGroup) {
      return;
    }

    if (activeGroup.pages.length === 0) {
      activeGroup.pages.push({ title: activeGroup.title, lines: activeGroup.preface });
      activeGroup.preface = [];
    } else if (compactMarkdown(activeGroup.preface)) {
      activeGroup.pages[0].lines = [...activeGroup.preface, "", ...activeGroup.pages[0].lines];
      activeGroup.preface = [];
    }

    groupDrafts.push(activeGroup);
    activeGroup = null;
  }

  function appendLine(line: string, preserveHeading = false) {
    if (activePage) {
      activePage.lines.push(
        preserveHeading ? line : line.replace(/^(#{4,6})(?=\s)/, (heading) => heading.slice(1)),
      );
    } else if (activeGroup) {
      activeGroup.preface.push(line);
    } else {
      intro.push(line);
    }
  }

  for (const line of markdown.replace(/\r\n?/g, "\n").split("\n")) {
    const fence = line.match(/^\s*(`{3,}|~{3,})/);
    if (fence) {
      const marker = fence[1][0] as "`" | "~";
      appendLine(line, true);
      fenceMarker = fenceMarker === marker ? null : fenceMarker ?? marker;
      continue;
    }

    if (fenceMarker) {
      appendLine(line, true);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+?)\s*$/);
    if (!heading) {
      appendLine(line);
      continue;
    }

    const level = heading[1].length;
    const title = trimHeading(heading[2]);

    if (level === 1 && !activeGroup && !activePage) {
      guideTitle = title;
      continue;
    }

    if (level === 2) {
      finishGroup();
      activeGroup = { title, preface: [], pages: [] };
      continue;
    }

    if (level === 3) {
      if (!activeGroup) {
        activeGroup = { title: "Guide", preface: [], pages: [] };
      }
      finishPage();
      activePage = { title, lines: [] };
      continue;
    }

    appendLine(line);
  }

  finishGroup();

  const usedSlugs = new Map<string, number>();
  const usedGroupSlugs = new Map<string, number>();
  const introMarkdown = compactMarkdown(intro);
  const normalizedGroups: GuideGroup[] = [];

  if (introMarkdown) {
    const welcomePage: GuidePage = {
      slug: createSlug("welcome", usedSlugs),
      title: "Welcome",
      groupTitle: "Start Here",
      markdown: introMarkdown,
      searchText: searchableText(`Welcome Start Here ${introMarkdown}`),
    };
    normalizedGroups.push({
      slug: createSlug("Start Here", usedGroupSlugs),
      title: "Start Here",
      pages: [welcomePage],
    });
  }

  for (const group of groupDrafts) {
    const pages = group.pages.map((page) => {
      const pageMarkdown = compactMarkdown(page.lines);
      return {
        slug: createSlug(page.title, usedSlugs),
        title: page.title,
        groupTitle: group.title,
        markdown: pageMarkdown,
        searchText: searchableText(`${page.title} ${group.title} ${pageMarkdown}`),
      };
    });

    normalizedGroups.push({
      slug: createSlug(group.title, usedGroupSlugs),
      title: group.title,
      pages,
    });
  }

  const pages = normalizedGroups.flatMap((group) => group.pages);
  return { title: guideTitle, groups: normalizedGroups, pages };
}
