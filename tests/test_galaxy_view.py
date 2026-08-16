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
        "risk",
        "verification",
        "changedOnly",
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
    assert "const mode='knowledge'" in rendered
    assert "Knowledge Galaxy" in rendered


def test_operational_galaxy_exposes_risk_verification_and_changed_filters() -> None:
    rendered = render_galaxy_view(
        {
            "nodes": [
                {
                    "id": "symbol:s1",
                    "kind": "symbol",
                    "label": "finalize_order",
                    "project_id": "p1",
                    "risk": "critical",
                    "verification_state": "contradicted",
                    "changed": True,
                    "contradicted": True,
                    "stale": False,
                }
            ],
            "edges": [],
            "summary": {
                "changed_nodes": 1,
                "missing_evidence_nodes": 0,
                "risk": {"critical": 1, "high": 0},
                "verification": {"stale": 0, "contradicted": 1},
            },
        },
        project_id="p1",
    )
    assert "Operational Galaxy" in rendered
    assert "const mode='operational'" in rendered
    assert 'aria-label="Filter by risk"' in rendered
    assert 'aria-label="Filter by verification"' in rendered
    assert 'id="changedOnly"' in rendered
    assert 'data-risk' in rendered
    assert 'data-verification' in rendered
    assert "riskPalette" in rendered
    assert "operational-galaxy.svg" in rendered
    assert "operational-galaxy.png" in rendered


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
