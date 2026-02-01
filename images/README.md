# Diagram Assets

This folder contains Mermaid diagram assets for "Redefining Data Engineering with AI". Diagrams are organized by chapter and cover topics such as workflow comparisons, team structures, agent architectures, and planning methodologies.

## Quick Start

### Convert a Mermaid diagram to PNG

Use the Claude Code slash command:

```
/mmd2png @chapter-3/<filename>.mmd
```

This command automatically:
1. Applies quality standards (theme, styling, formatting)
2. Generates a high-resolution PNG suitable for book publishing
3. Reports the output file size

### Manual conversion

```bash
mmdc -i <file>.mmd -o <file>.png -w 2400 -H 1000 -b white -s 2
```

## Quality Standards

All diagrams follow these standards (see `CLAUDE.md` for details):

- **Horizontal layout** (`flowchart LR` / `graph LR`) for book page fit
- **Theme configuration** with 16px Arial font
- **Subgraph IDs** for consistent styling
- **Colored borders** on subgraph containers
- **2px stroke width** for visibility
- **HTML italic tags** for aliases (e.g., `<i>a.k.a. DRD</i>`)

## File Structure

```
images/
├── CLAUDE.md                # Diagram quality guidelines for Claude Code
├── README.md                # This file
├── .claude/
│   └── commands/
│       └── mmd2png.md       # Slash command for PNG generation
├── chapter-2/
│   └── .gitkeep             # Placeholder for future diagrams
└── chapter-3/
    ├── *.mmd                # Mermaid source files
    └── *.png                # Rendered diagram images
```

## Prerequisites

- [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`npm install -g @mermaid-js/mermaid-cli`)
- [Claude Code](https://claude.ai/code) for using slash commands
