"""Markdown viewer component with Mermaid diagram support.

This module provides a custom NiceGUI component that renders markdown
content with proper formatting and Mermaid diagram rendering.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    pass

def _ensure_mermaid_initialized() -> None:
    """Ensure Mermaid.js is loaded for this page.

    Note: We always add the script because NiceGUI SPA navigation
    may create new pages that don't have the script loaded.
    The JavaScript itself is idempotent and won't reload mermaid
    if it's already present.
    """
    # Add CSS styles to head (idempotent - browser handles duplicates)
    ui.add_head_html("""
    <style>
        .mermaid-container {
            background-color: #ffffff;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            margin: 16px 0;
            overflow-x: auto;
            min-height: 50px;
        }
        .mermaid-pending, .mermaid-rendering {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100px;
            color: #666;
            font-style: italic;
        }
        .mermaid-pending::before {
            content: "Loading diagram...";
        }
        .mermaid-rendering::before {
            content: "Rendering...";
        }
        .mermaid-rendered {
            display: flex;
            justify-content: center;
        }
        .mermaid-rendered svg {
            max-width: 100%;
            height: auto;
        }
        .mermaid-error {
            color: #c62828;
            background-color: #ffebee;
            padding: 12px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }
        .markdown-content {
            width: 100%;
        }
        .markdown-content h1 { font-size: 2em; font-weight: 600; margin-top: 24px; margin-bottom: 16px; padding-bottom: 0.3em; border-bottom: 1px solid #e0e0e0; }
        .markdown-content h2 { font-size: 1.5em; font-weight: 600; margin-top: 24px; margin-bottom: 16px; padding-bottom: 0.3em; border-bottom: 1px solid #e0e0e0; }
        .markdown-content h3 { font-size: 1.25em; font-weight: 600; margin-top: 24px; margin-bottom: 16px; }
        .markdown-content h4 { font-size: 1em; font-weight: 600; margin-top: 24px; margin-bottom: 16px; }
        .markdown-content p { margin-top: 0; margin-bottom: 16px; line-height: 1.6; }
        .markdown-content ul, .markdown-content ol { padding-left: 2em; margin-bottom: 16px; }
        .markdown-content li { margin-bottom: 4px; }
        .markdown-content table { border-collapse: collapse; width: 100%; margin-bottom: 16px; }
        .markdown-content th, .markdown-content td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        .markdown-content th { background-color: #f5f5f5; font-weight: 600; }
        .markdown-content tr:nth-child(even) { background-color: #fafafa; }
        .markdown-content code { background-color: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
        .markdown-content pre { background-color: #f5f5f5; padding: 16px; border-radius: 6px; overflow-x: auto; margin-bottom: 16px; }
        .markdown-content pre code { background: none; padding: 0; }
        .markdown-content blockquote { border-left: 4px solid #ddd; padding-left: 16px; margin: 0 0 16px 0; color: #666; }
        .markdown-content hr { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
        .markdown-content a { color: #1976d2; text-decoration: none; }
        .markdown-content a:hover { text-decoration: underline; }
    </style>
    """)

    # Add Mermaid.js script to body - using regular script for better compatibility
    ui.add_body_html("""
    <script>
        // Load mermaid if not already loaded
        if (!window.mermaidLoading && !window.mermaid) {
            window.mermaidLoading = true;
            var script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
            script.onload = function() {
                window.mermaid.initialize({
                    startOnLoad: false,
                    theme: 'default',
                    securityLevel: 'loose',
                    flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
                    sequence: { useMaxWidth: true },
                    er: { useMaxWidth: true },
                    gantt: { useMaxWidth: true },
                });
                console.log('Mermaid loaded and initialized');
                window.renderAllMermaid();
            };
            document.head.appendChild(script);
        }

        // Function to render a single mermaid element
        window.renderMermaidElement = function(el) {
            if (!el || !el.classList.contains('mermaid-pending')) {
                return;
            }

            if (!window.mermaid) {
                console.log('Mermaid not loaded yet, deferring render...');
                setTimeout(function() { window.renderMermaidElement(el); }, 200);
                return;
            }

            var content = el.textContent;
            console.log('Rendering diagram:', content.substring(0, 50) + '...');

            el.classList.remove('mermaid-pending');
            el.classList.add('mermaid-rendering');

            try {
                var id = 'mermaid-' + Math.random().toString(36).substr(2, 9);
                window.mermaid.render(id, content)
                    .then(function(result) {
                        el.innerHTML = result.svg;
                        el.classList.remove('mermaid-rendering');
                        el.classList.add('mermaid-rendered');
                        console.log('Diagram rendered successfully');
                    })
                    .catch(function(err) {
                        console.error('Mermaid render error:', err);
                        el.innerHTML = '<div class="mermaid-error">Mermaid Error: ' + err.message + '</div>';
                        el.classList.remove('mermaid-rendering');
                        el.classList.add('mermaid-error-container');
                    });
            } catch (err) {
                console.error('Mermaid exception:', err);
                el.innerHTML = '<div class="mermaid-error">Mermaid Error: ' + err.message + '</div>';
            }
        };

        // Function to render all pending mermaid diagrams
        window.renderAllMermaid = function() {
            var pending = document.querySelectorAll('.mermaid-pending');
            console.log('renderAllMermaid called, found ' + pending.length + ' pending diagrams');

            if (!window.mermaid) {
                console.log('Mermaid not loaded yet, will retry...');
                setTimeout(function() { window.renderAllMermaid(); }, 200);
                return;
            }

            pending.forEach(function(el) {
                window.renderMermaidElement(el);
            });
        };

        // Set up MutationObserver to automatically render new mermaid diagrams
        // This handles the timing issue where elements are added to DOM after renderAllMermaid is called
        if (!window.mermaidObserver) {
            window.mermaidObserver = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            // Check if the added node itself is a mermaid-pending element
                            if (node.classList && node.classList.contains('mermaid-pending')) {
                                console.log('MutationObserver: Found new mermaid-pending element');
                                window.renderMermaidElement(node);
                            }
                            // Check for mermaid-pending elements within added subtrees
                            if (node.querySelectorAll) {
                                var pending = node.querySelectorAll('.mermaid-pending');
                                if (pending.length > 0) {
                                    console.log('MutationObserver: Found ' + pending.length + ' new mermaid-pending elements in subtree');
                                    pending.forEach(function(el) {
                                        window.renderMermaidElement(el);
                                    });
                                }
                            }
                        }
                    });
                });
            });

            // Start observing the document body for added nodes
            window.mermaidObserver.observe(document.body, {
                childList: true,
                subtree: true
            });
            console.log('MutationObserver set up for mermaid diagrams');
        }
    </script>
    """)


class MarkdownViewer:
    """A markdown viewer component with Mermaid diagram support.

    This component:
    - Renders markdown content using NiceGUI's built-in markdown renderer
    - Automatically detects and renders Mermaid diagrams
    - Supports view mode toggle between rendered and raw
    - Handles large content with scrolling
    """

    def __init__(
        self,
        content: str = "",
        max_height: str = "600px",
        show_raw_toggle: bool = True,
    ) -> None:
        """Initialize the markdown viewer.

        Args:
            content: Initial markdown content to display.
            max_height: Maximum height of the viewer (CSS value).
            show_raw_toggle: Whether to show a toggle for raw/rendered view.
        """
        self.content = content
        self.max_height = max_height
        self.show_raw_toggle = show_raw_toggle
        self._show_raw = False
        self._container: ui.element | None = None
        self._content_area: ui.element | None = None
        self._viewer_id = str(uuid.uuid4())[:8]

    def render(self) -> ui.element:
        """Render the markdown viewer component.

        Returns:
            The container element.
        """
        # Ensure mermaid is initialized
        _ensure_mermaid_initialized()

        with ui.column().classes("w-full") as container:
            self._container = container

            # Toggle buttons
            if self.show_raw_toggle:
                with ui.row().classes("w-full justify-end gap-2 mb-2"):
                    self._rendered_btn = ui.button(
                        "Rendered",
                        on_click=lambda: self._set_view_mode(False),
                    ).props("flat dense")

                    self._raw_btn = ui.button(
                        "Raw",
                        on_click=lambda: self._set_view_mode(True),
                    ).props("flat dense")

                    self._update_button_styles()

            # Content area with scroll - use height for calc() values to fill space
            height_style = (
                f"height: {self.max_height};"
                if "calc" in self.max_height or "vh" in self.max_height
                else f"max-height: {self.max_height};"
            )
            with ui.scroll_area().classes("w-full").style(height_style):
                self._content_area = ui.column().classes("w-full p-2")
                self._render_content()

        return container

    def _update_button_styles(self) -> None:
        """Update toggle button styles based on current mode."""
        if hasattr(self, "_rendered_btn"):
            if self._show_raw:
                self._rendered_btn.classes(remove="text-primary", add="text-grey")
                self._raw_btn.classes(remove="text-grey", add="text-primary")
            else:
                self._rendered_btn.classes(remove="text-grey", add="text-primary")
                self._raw_btn.classes(remove="text-primary", add="text-grey")

    def _set_view_mode(self, show_raw: bool) -> None:
        """Set the view mode and re-render."""
        self._show_raw = show_raw
        self._update_button_styles()
        self._render_content()

    def _render_content(self) -> None:
        """Render the content based on current view mode."""
        if self._content_area is None:
            return

        self._content_area.clear()

        with self._content_area:
            if self._show_raw:
                # Raw view - show as code
                ui.code(self.content, language="markdown").classes("w-full")
            else:
                # Rendered view - parse and render markdown with Mermaid
                try:
                    self._render_markdown_with_mermaid(self.content)
                except Exception as e:
                    # If rendering fails, show error and fall back to code view
                    ui.label(f"Markdown rendering error: {e}").classes("text-red-500")
                    ui.code(self.content, language="markdown").classes("w-full")

    def _render_markdown_with_mermaid(self, content: str) -> None:
        """Render markdown content, handling Mermaid diagrams specially.

        Args:
            content: Markdown content to render.
        """
        # Strip outer markdown code fence wrapper FIRST before detecting mermaid blocks
        # This handles cases where LLM wraps entire output in ```markdown ... ```
        content = content.strip()
        content = re.sub(r"^```(?:markdown)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

        # Split content by mermaid code blocks
        mermaid_pattern = re.compile(
            r"```mermaid\s*\n(.*?)```",
            re.DOTALL | re.IGNORECASE,
        )

        parts = []
        last_end = 0

        for match in mermaid_pattern.finditer(content):
            # Add markdown part before this mermaid block
            if match.start() > last_end:
                md_content = content[last_end : match.start()].strip()
                if md_content:
                    parts.append(("markdown", md_content))

            # Add mermaid diagram
            diagram_content = match.group(1).strip()
            parts.append(("mermaid", diagram_content))
            last_end = match.end()

        # Add remaining markdown after last mermaid block
        if last_end < len(content):
            md_content = content[last_end:].strip()
            if md_content:
                parts.append(("markdown", md_content))

        # If no mermaid blocks found, render entire content as markdown
        if not parts:
            parts.append(("markdown", content))

        # Render each part
        for part_type, part_content in parts:
            if part_type == "markdown":
                self._render_markdown_part(part_content)
            else:
                self._render_mermaid_diagram(part_content)

        # Trigger mermaid rendering after a short delay
        ui.run_javascript(
            "setTimeout(() => window.renderAllMermaid && window.renderAllMermaid(), 100);"
        )

    def _render_markdown_part(self, content: str) -> None:
        """Render a markdown content part by converting to HTML.

        Args:
            content: Markdown content to render.
        """
        import markdown2  # type: ignore[import-untyped]

        # Convert markdown to HTML using markdown2
        # Note: Don't use fenced-code-blocks as it can cause issues with code highlighting
        html_content = markdown2.markdown(
            content,
            extras=["tables", "cuddled-lists", "header-ids", "strike"],
        )

        html_str = str(html_content)

        # Render with inline styles for proper markdown appearance
        styled_html = f"""
        <div class="markdown-rendered" style="
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        ">
            <style>
                .markdown-rendered h1 {{ font-size: 1.8em; font-weight: 600; margin: 0.5em 0; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
                .markdown-rendered h2 {{ font-size: 1.4em; font-weight: 600; margin: 0.6em 0; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
                .markdown-rendered h3 {{ font-size: 1.2em; font-weight: 600; margin: 0.8em 0; }}
                .markdown-rendered h4 {{ font-size: 1em; font-weight: 600; margin: 1em 0; }}
                .markdown-rendered p {{ margin: 0.8em 0; }}
                .markdown-rendered ul, .markdown-rendered ol {{ margin: 0.8em 0; padding-left: 2em; }}
                .markdown-rendered li {{ margin: 0.3em 0; }}
                .markdown-rendered table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }}
                .markdown-rendered th, .markdown-rendered td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .markdown-rendered th {{ background-color: #f5f5f5; font-weight: 600; }}
                .markdown-rendered tr:nth-child(even) {{ background-color: #fafafa; }}
                .markdown-rendered code {{ background-color: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 0.9em; }}
                .markdown-rendered pre {{ background-color: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }}
                .markdown-rendered pre code {{ background: none; padding: 0; }}
                .markdown-rendered strong {{ font-weight: 600; }}
                .markdown-rendered em {{ font-style: italic; }}
                .markdown-rendered blockquote {{ border-left: 4px solid #ddd; margin: 1em 0; padding-left: 1em; color: #666; }}
            </style>
            {html_str}
        </div>
        """
        ui.html(styled_html, sanitize=False)

    def _render_mermaid_diagram(self, diagram_content: str) -> None:
        """Render a Mermaid diagram.

        Args:
            diagram_content: The Mermaid diagram definition.
        """
        import html

        diagram_id = f"mermaid-{self._viewer_id}-{uuid.uuid4().hex[:8]}"

        # Escape HTML entities in the diagram content to safely embed in HTML
        escaped_content = html.escape(diagram_content)

        # Create the mermaid container with the diagram content directly embedded
        # The JavaScript will find elements with class "mermaid-pending" and render them
        # Using ui.html to directly set the textContent as inner text of the div
        mermaid_html = f'''
        <div class="mermaid-container">
            <div id="{diagram_id}" class="mermaid-pending">{escaped_content}</div>
        </div>
        '''
        ui.html(mermaid_html, sanitize=False)

    def update_content(self, content: str) -> None:
        """Update the displayed content.

        Args:
            content: New markdown content.
        """
        self.content = content
        if self._content_area is not None:
            self._render_content()


def markdown_with_mermaid(
    content: str,
    max_height: str = "600px",
    show_raw_toggle: bool = True,
) -> MarkdownViewer:
    """Create and render a markdown viewer with Mermaid support.

    Args:
        content: Markdown content to display.
        max_height: Maximum height of the viewer.
        show_raw_toggle: Whether to show raw/rendered toggle.

    Returns:
        The MarkdownViewer instance.
    """
    viewer = MarkdownViewer(
        content=content,
        max_height=max_height,
        show_raw_toggle=show_raw_toggle,
    )
    viewer.render()
    return viewer
