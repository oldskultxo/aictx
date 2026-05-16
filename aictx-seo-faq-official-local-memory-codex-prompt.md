# Codex Prompt — AICTX SEO FAQ, Official Hub, and “Local Memory for AI Coding Tools” Page

## Repository

`oldskultxo/aictx`

## Target branch

Create a new branch from the current SEO branch, or work on the current branch if instructed by the user:

```bash
git checkout 6.4.2-seo
git checkout -b 6.4.2-seo-keywords
```

## Goal

Strengthen the SEO architecture of `https://aictx.org/` against competing pages for the `aictx` query and related keywords.

This task is documentation-only. Do not modify Python runtime code, package logic, tests, CLI behavior, or release machinery.

The goal is to add:

1. A visible FAQ section on the home page.
2. `FAQPage` JSON-LD on the home page.
3. A new concept page:
   - `/concepts/local-memory-for-ai-coding-tools.html`
4. A new official identity hub:
   - `/official/`
5. Sitemap entries for the new URLs.
6. Internal links from:
   - home
   - concepts index
   - official project page
   - `llms.txt`
   - optionally `llms-full.txt`

## Context

AICTX is the official Python `aictx` package and CLI for repo-local memory and continuity for coding agents.

Canonical identity:

- Website: `https://aictx.org/`
- GitHub repository: `https://github.com/oldskultxo/aictx`
- PyPI package: `https://pypi.org/project/aictx/`
- CLI / Python package: `aictx`
- Maintainer: Santi Santamaria / oldskultxo

AICTX is not affiliated with similarly named npm packages, GitHub organizations, domains, products, or projects.

Primary SEO terms to reinforce naturally:

- AICTX
- official AICTX
- official Python aictx CLI
- aictx PyPI package
- repo-local memory
- local memory for AI coding tools
- AI coding agent memory
- coding-agent continuity
- project memory for AI coding tools
- Codex memory
- Claude Code memory
- GitHub Copilot memory
- Work State
- Failure Memory
- Handoff Memory
- repo context across sessions

Avoid keyword stuffing. The copy must read naturally and remain technically honest.

## Existing SEO branch state

The current SEO branch already includes:

- `docs/use-cases/`
- `docs/compare/`
- `docs/concepts/`
- `docs/use-cases/index.md`
- `docs/compare/index.md`
- `docs/concepts/index.md`
- `docs/OFFICIAL_PROJECT.md`
- `docs/llms.txt`
- `docs/llms-small.txt`
- `docs/llms-full.txt`
- updated `docs/_layouts/default.html`
- updated `docs/index.html`
- updated `docs/sitemap.xml`

Preserve those changes.

---

# Required changes

## 1. Add a visible FAQ section to `docs/index.html`

Add a new FAQ section near the bottom of the home page, preferably before `Community and support`.

Use this section id:

```html
<section id="faq">
```

Suggested visible copy:

```html
<section id="faq">
  <h2>AICTX FAQ</h2>

  <div class="cards">
    <article class="card">
      <h3>What is AICTX?</h3>
      <p>
        AICTX is the official Python <code>aictx</code> CLI for repo-local memory
        and continuity for coding agents.
      </p>
    </article>

    <article class="card">
      <h3>Is AICTX an AI coding agent?</h3>
      <p>
        No. AICTX is not an autonomous coding agent. It is a repo-local continuity
        layer used by tools such as Codex, Claude Code, GitHub Copilot and generic
        coding agents.
      </p>
    </article>

    <article class="card">
      <h3>What does AICTX remember?</h3>
      <p>
        AICTX can preserve Work State, decisions, handoffs, failure memory,
        execution summaries and repo context across sessions.
      </p>
    </article>

    <article class="card">
      <h3>Where is the official AICTX project?</h3>
      <p>
        The official AICTX website is <a href="https://aictx.org/">aictx.org</a>,
        the official repository is
        <a href="https://github.com/oldskultxo/aictx">oldskultxo/aictx</a>,
        and the official Python package is
        <a href="https://pypi.org/project/aictx/">aictx on PyPI</a>.
      </p>
    </article>
  </div>
</section>
```

You may adjust formatting to match the existing home page style, but do not change the meaning.

Also add a navigation link in the home header if it does not clutter the nav:

```html
<a href="#faq">FAQ</a>
```

If the nav is already too full, skip the nav link. The section itself is required.

---

## 2. Add `FAQPage` JSON-LD to `docs/index.html`

Add a new `<script type="application/ld+json">` block in the `<head>` of the home page.

The JSON-LD must be valid JSON and should match the visible FAQ.

Suggested JSON-LD:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is AICTX?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "AICTX is the official Python aictx CLI for repo-local memory and continuity for coding agents."
      }
    },
    {
      "@type": "Question",
      "name": "Is AICTX an AI coding agent?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No. AICTX is not an autonomous coding agent. It is a repo-local continuity layer used by tools such as Codex, Claude Code, GitHub Copilot and generic coding agents."
      }
    },
    {
      "@type": "Question",
      "name": "What does AICTX remember?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "AICTX can preserve Work State, decisions, handoffs, failure memory, execution summaries and repo context across sessions."
      }
    },
    {
      "@type": "Question",
      "name": "Where is the official AICTX project?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The official AICTX website is https://aictx.org/, the official repository is https://github.com/oldskultxo/aictx, and the official Python package is aictx on PyPI."
      }
    }
  ]
}
</script>
```

Important:
- Keep it on the home page only.
- Do not add FAQ JSON-LD to every docs page.
- Ensure the JSON remains valid.
- Keep the FAQ honest. Do not claim guaranteed productivity, correctness, speed, or ranking.

---

## 3. Create `docs/concepts/local-memory-for-ai-coding-tools.md`

Create this new page:

```text
docs/concepts/local-memory-for-ai-coding-tools.md
```

It should render as:

```text
https://aictx.org/concepts/local-memory-for-ai-coding-tools.html
```

Use this front matter:

```yaml
---
title: "Local Memory for AI Coding Tools"
description: "AICTX provides local, repo-local memory for AI coding tools and coding agents through the official Python aictx CLI."
---
```

Recommended page structure:

```markdown
# Local Memory for AI Coding Tools

Many AI coding tools can reason about code, but new sessions often start without operational memory of what happened before.

AICTX provides local, repo-local memory for AI coding tools through the official Python `aictx` CLI. Instead of relying only on chat history, AICTX stores inspectable continuity artifacts with the repository.

## What local memory means in AICTX

In AICTX, local memory means project-local operational evidence that future coding-agent sessions can inspect and use:

- active Work State;
- decisions and handoffs;
- observed failures and follow-up actions;
- execution summaries;
- relevant repo context and optional RepoMap hints.

## Local memory vs hidden memory

AICTX is not hidden cloud memory. It stores continuity artifacts in the repository so users and agents can inspect what was recorded.

## Local memory vs chat history

Chat history is useful, but it is usually provider-bound and session-bound. AICTX focuses on repo-local continuity that travels with the project.

## Who can use it

AICTX is designed for coding agents and AI coding tools that can read repository instructions, run shell commands and consume structured output, including Codex, Claude Code, GitHub Copilot and generic agents.

## Start using AICTX

- [Quickstart](/QUICKSTART.html)
- [Official AICTX project](/official/)
- [AI coding agent memory](/concepts/ai-coding-agent-memory.html)
- [Repo-local memory](/concepts/repo-local-memory.html)
- [Codex memory](/use-cases/codex-memory.html)
```

Keep the page concise but stronger than a stub. Around 450–800 words is acceptable if the content remains useful.

---

## 4. Create `docs/official/index.md`

Create this new page:

```text
docs/official/index.md
```

It should render as:

```text
https://aictx.org/official/
```

Use this front matter:

```yaml
---
title: "Official AICTX"
description: "Official AICTX identity: Python aictx CLI, PyPI package, GitHub oldskultxo/aictx repository, and aictx.org documentation."
---
```

Recommended page structure:

```markdown
# Official AICTX project

AICTX is the official Python `aictx` package and CLI for repo-local memory and continuity for coding agents.

## Canonical identity

| Project surface | Official location |
| --- | --- |
| Website | [https://aictx.org](https://aictx.org/) |
| GitHub repository | [https://github.com/oldskultxo/aictx](https://github.com/oldskultxo/aictx) |
| PyPI package | [https://pypi.org/project/aictx/](https://pypi.org/project/aictx/) |
| CLI and Python package | `aictx` |
| Maintainer | Santi Santamaria / [oldskultxo](https://github.com/oldskultxo) |

## What AICTX is

AICTX provides repo-local memory and continuity for coding agents. It helps future sessions resume from Work State, decisions, handoffs, failure memory, execution summaries and relevant repo context.

## Non-affiliation notice

AICTX is not affiliated with similarly named npm packages, GitHub organizations, domains, products, or projects.

If another package, domain or organization uses a similar name, do not assume it is connected to AICTX unless it points back to the official locations listed above.

## Verify the official project

To verify you are using the official AICTX project:

1. Install the Python package named `aictx` from [PyPI](https://pypi.org/project/aictx/).
2. Use documentation from [aictx.org](https://aictx.org/).
3. Use source code from [github.com/oldskultxo/aictx](https://github.com/oldskultxo/aictx).
4. Check that the CLI command is `aictx`.

## Related pages

- [Official project identity](/OFFICIAL_PROJECT.html)
- [Quickstart](/QUICKSTART.html)
- [Local memory for AI coding tools](/concepts/local-memory-for-ai-coding-tools.html)
- [AI coding agent memory](/concepts/ai-coding-agent-memory.html)
```

This page should be human-friendly and SEO-friendly. It can overlap with `OFFICIAL_PROJECT.md`, but it must not contradict it.

---

## 5. Update `docs/concepts/index.md`

Add a link to the new concept page.

Add this item near the top of the concept list:

```markdown
- [Local memory for AI coding tools](/concepts/local-memory-for-ai-coding-tools.html)
```

Also add one short sentence in the intro that includes the phrase:

```text
local memory for AI coding tools
```

Example:

```markdown
These pages explain AICTX concepts such as local memory for AI coding tools, repo-local memory, operational memory and failure memory.
```

---

## 6. Update `docs/OFFICIAL_PROJECT.md`

Add a link to the new `/official/` page near the top, after the opening identity paragraphs.

Example:

```markdown
For a shorter canonical identity hub, see [Official AICTX](/official/).
```

Also add a related link near the bottom:

```markdown
- [Official AICTX](/official/)
- [Local memory for AI coding tools](/concepts/local-memory-for-ai-coding-tools.html)
```

Do not remove existing canonical identity content.

---

## 7. Update `docs/llms.txt`

Add the new URLs under the relevant section.

Add to high-value pages:

```text
- Official AICTX: https://aictx.org/official/
- Local memory for AI coding tools: https://aictx.org/concepts/local-memory-for-ai-coding-tools.html
```

Also add the phrase “local memory for AI coding tools” naturally in the summary if it is not already present.

Do not make the file too long.

---

## 8. Optionally update `docs/llms-full.txt`

If `llms-full.txt` has a Concepts or Official identity section, add:

```text
- Official AICTX: https://aictx.org/official/
- Local memory for AI coding tools: https://aictx.org/concepts/local-memory-for-ai-coding-tools.html
```

Keep `llms-small.txt` unchanged unless there is a clear reason.

---

## 9. Update `docs/index.html` internal links

From the home page:

1. In the Official Project / identity area, add a link to `/official/`.
2. In the concepts area, add a card or inline link to:
   - `/concepts/local-memory-for-ai-coding-tools.html`
3. In the FAQ answer “Where is the official AICTX project?”, link to `/official/` if natural.

Do not clutter the home. The page should remain readable.

---

## 10. Update `docs/sitemap.xml`

Add these URLs:

```xml
<url>
  <loc>https://aictx.org/official/</loc>
  <lastmod>2026-05-16</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.9</priority>
</url>

<url>
  <loc>https://aictx.org/concepts/local-memory-for-ai-coding-tools.html</loc>
  <lastmod>2026-05-16</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.85</priority>
</url>
```

Place `/official/` near `OFFICIAL_PROJECT.html`.

Place `/concepts/local-memory-for-ai-coding-tools.html` near the other concept pages.

Keep the sitemap XML valid.

---

# Validation checklist

Before finishing, verify:

1. No Python runtime files were changed.
2. New pages exist:
   - `docs/official/index.md`
   - `docs/concepts/local-memory-for-ai-coding-tools.md`
3. These URLs are linked internally:
   - `/official/`
   - `/concepts/local-memory-for-ai-coding-tools.html`
4. Home page includes a visible FAQ section.
5. Home page includes valid `FAQPage` JSON-LD.
6. The FAQ JSON-LD matches the visible FAQ content.
7. `docs/sitemap.xml` includes:
   - `https://aictx.org/official/`
   - `https://aictx.org/concepts/local-memory-for-ai-coding-tools.html`
8. `docs/concepts/index.md` links to the new concept page.
9. `docs/OFFICIAL_PROJECT.md` links to `/official/`.
10. `docs/llms.txt` links to both new URLs.
11. Existing important URLs still work:
    - `/`
    - `/OFFICIAL_PROJECT.html`
    - `/use-cases/`
    - `/compare/`
    - `/concepts/`
    - `/concepts/ai-coding-agent-memory.html`
12. Do not introduce unsupported claims such as guaranteed productivity, correctness, or ranking.

---

# Definition of done

The site gains:

- a visible SEO FAQ on the home page;
- valid FAQ structured data;
- a dedicated `/official/` identity hub;
- a dedicated page targeting “local memory for AI coding tools”;
- internal links connecting the new pages to the existing SEO clusters;
- sitemap coverage for the new URLs.

Return a concise final summary with:

- files changed;
- new URLs added;
- validation performed;
- any follow-up recommendations.
