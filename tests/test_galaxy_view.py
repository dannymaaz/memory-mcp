from __future__ import annotations

from persistent_memory_mcp.galaxy_view import render_galaxy_view


def test_galaxy_renderer_escapes_embedded_graph_content() -> None:
    rendered = render_galaxy_view(
        {
            "nodes": [
                {
                    "id": "tasks:t1",
                    "kind": "task",
                    "label": "</script><script>alert(1)</script>",
                    "project_id": "p1",
                }
            ],
            "edges": [],
        },
        project_id='"><img src=x>',
    )
    assert "</script><script>alert(1)</script>" not in rendered
    assert "\\u003c/script>\\u003cscript>alert(1)\\u003c/script>" in rendered
    assert '"><img src=x>' not in rendered
    assert "&quot;&gt;&lt;img src=x&gt;" in rendered


def test_galaxy_renderer_exposes_navigation_controls() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    control_ids = {
        "search",
        "kind",
        "zoomIn",
        "zoomOut",
        "reset",
        "fit",
        "layout",
        "focus",
        "clearFocus",
        "exportSvg",
        "exportPng",
    }
    assert all(f'id="{control_id}"' in rendered for control_id in control_ids)
    assert 'role="img"' in rendered
    assert 'aria-label="Search nodes"' in rendered
    assert 'aria-label="Filter by type"' in rendered


def test_galaxy_renderer_includes_interactive_layout_features() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    for marker in (
        "function runLayout",
        "function startNodeDrag",
        "function fitView",
        "function focusSelection",
        "requestAnimationFrame",
        "pinned.add",
        "pointermove",
    ):
        assert marker in rendered


def test_galaxy_renderer_includes_minimap_and_persistent_layout() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []}, project_id="p1")
    for marker in (
        'id="minimap"',
        "function drawMinimap",
        "localStorage.getItem(storageKey)",
        "localStorage.setItem(storageKey",
        "const storageKey='memory-mcp-galaxy:'",
        "String('p1')",
    ):
        assert marker in rendered


def test_galaxy_renderer_includes_svg_and_png_exports() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    for marker in (
        "function exportSvg",
        "function exportPng",
        "knowledge-galaxy.svg",
        "knowledge-galaxy.png",
    ):
        assert marker in rendered


def test_galaxy_renderer_uses_safe_text_assignment_for_dynamic_content() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    assert "textContent=n.label" in rendered
    assert "details.textContent=JSON.stringify" in rendered
