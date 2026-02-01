# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This directory contains diagram assets for "Redefining Data Engineering with AI". Diagrams are organized into chapter-specific subdirectories (`chapter-2/`, `chapter-3/`, etc.) and rendered from Mermaid source files to PNG images.

## Diagram Files

All diagrams are written in Mermaid syntax (`.mmd` files) and rendered to PNG images.

### Generating Diagrams

Use mermaid-cli (`mmdc`) to render diagrams. For high-quality, book-friendly output:

```bash
mmdc -i <file>.mmd -o <file>.png -w 2400 -H 1000 -b white -s 2
```

Key flags:
- `-w 2400` / `-H 1000`: Wide aspect ratio (2.4:1) to fit book pages
- `-b white`: White background
- `-s 2`: Scale factor for higher resolution

### Horizontal Layout for Book Pages

**ALWAYS use horizontal (left-to-right) layouts** so diagrams fit on book pages:

```mermaid
# Use LR (left-to-right) instead of TD (top-down)
flowchart LR
graph LR
```

For complex diagrams with multiple phases/sections:
- Main flow should be horizontal (LR)
- Use `direction TB` inside subgraphs for vertical detail within each section

### Diagram Quality Standards

**ALWAYS apply these standards to all `.mmd` files before generating PNGs:**

#### 1. Add theme configuration at the top of the `.mmd` file:
```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px', 'fontFamily': 'arial'}}}%%
```

#### 2. Give subgraphs an ID for styling:
```mermaid
# Before
subgraph "Software Project Artifacts"

# After
subgraph software["Software Project Artifacts"]
```

#### 3. Use `direction TB` only when you have MULTIPLE side-by-side subgraphs:
- For diagrams with 2+ subgraphs arranged horizontally, use `direction TB` inside each for vertical detail
- For single subgraphs or simple flowcharts, do NOT use `direction TB` - let content flow horizontally
- Decision trees and linear flows should always be fully horizontal (no subgraphs needed)

```mermaid
# Example: Multi-subgraph layout (Inputs → Process → Outputs)
subgraph data["Data Engineering Artifacts"]
    direction TB
    D1[...] --> D2[...]
end
```

#### 4. Replace unicode separators with HTML italic tags for aliases:
```mermaid
# Before
D1[Data Requirements Document<br/>━━━━━━━━━━━━━━━━━━<br/>a.k.a. DRD, Data Spec]

# After
D1["Data Requirements Document<br/><i>a.k.a. DRD, Data Spec</i>"]
```

#### 5. Add `stroke-width:2px` to all styles for better visibility:
```mermaid
# Before
style D1 fill:#a8e6cf,stroke:#333

# After
style D1 fill:#a8e6cf,stroke:#333,stroke-width:2px
```

#### 6. Style subgraph containers with colored borders:
```mermaid
style software fill:#e8f4f8,stroke:#2196F3,stroke-width:2px
style data fill:#fff8e1,stroke:#FF9800,stroke-width:2px
```

#### 7. Chain arrows for cleaner syntax:
```mermaid
# Before
D1 --> D2
D2 --> D3
D3 --> D4

# After
D1 --> D2 --> D3 --> D4
```
