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
    assert 'id="search"' in rendered
    assert 'id="kind"' in rendered
    assert 'id="zoomIn"' in rendered
    assert 'id="zoomOut"' in rendered
    assert 'id="focus"' in rendered
    assert 'role="img"' in rendered
