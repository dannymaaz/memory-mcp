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
    for control in (
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
    ):
        assert f'id="{control}"' in rendered
    assert 'role="img"' in rendered
    assert 'aria-label="Search nodes"' in rendered
    assert 'aria-label="Filter by type"' in rendered


def test_galaxy_renderer_includes_force_layout_and_drag_support() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    assert "function runLayout(" in rendered
    assert "requestAnimationFrame(step)" in rendered
    assert "function startNodeDrag(" in rendered
    assert "pinned.add(nodeDrag.id)" in rendered
    assert "pointermove" in rendered


def test_galaxy_renderer_includes_minimap_and_persistent_layout() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []}, project_id="p1")
    assert 'id="minimap"' in rendered
    assert "function drawMinimap(" in rendered
    assert "localStorage.getItem(storageKey)" in rendered
    assert "localStorage.setItem(storageKey" in rendered
    assert "memory-mcp-galaxy:p1" in rendered


def test_galaxy_renderer_includes_svg_and_png_exports() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    assert "function exportSvg(" in rendered
    assert "function exportPng(" in rendered
    assert "knowledge-galaxy.svg" in rendered
    assert "knowledge-galaxy.png" in rendered


def test_galaxy_renderer_uses_text_content_for_node_labels() -> None:
    rendered = render_galaxy_view({"nodes": [], "edges": []})
    assert "t.textContent=n.label" in rendered
    assert "details.textContent=JSON.stringify" in rendered
    assert "innerHTML" not in rendered
