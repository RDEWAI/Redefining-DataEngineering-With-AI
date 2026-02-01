# Convert Mermaid to PNG

Convert a Mermaid diagram file to PNG with book-quality settings.

## Arguments
- `$ARGUMENTS` - Path to the .mmd file to convert

## Instructions

1. Read the CLAUDE.md file in this project to understand the diagram quality standards
2. Read the .mmd file at `$ARGUMENTS`
3. Apply quality standards from CLAUDE.md if not already present:
   - Add theme configuration at the top if missing
   - Give subgraphs an ID for styling
   - Use `direction TB` inside subgraphs ONLY when there are multiple side-by-side subgraphs (e.g., Inputs → Process → Outputs). For single-flow diagrams like decision trees, keep everything horizontal without subgraphs.
   - Replace unicode separators with HTML italic tags
   - Add `stroke-width:2px` to all styles
   - Style subgraph containers with colored borders
   - Chain arrows for cleaner syntax
4. Generate PNG using: `mmdc -i <file>.mmd -o <file>.png -w 2400 -H 1000 -b white -s 2`
5. Verify the PNG was created and report the file size
