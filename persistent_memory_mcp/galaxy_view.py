"""Dependency-free browser renderer for the bounded knowledge graph."""

from __future__ import annotations

import html
import json
from typing import Any, Mapping


def render_galaxy_view(graph: Mapping[str, Any], *, project_id: str | None = None) -> str:
    """Render an escaped, self-contained SVG galaxy view."""
    graph_json = json.dumps(graph, ensure_ascii=False, default=str).replace("<", "\\u003c")
    project = html.escape(project_id or "", quote=True)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Knowledge Galaxy</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;background:#07101f;color:#e8f0fb}}
header{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:14px 18px;border-bottom:1px solid #24344d;background:#0d1829}}
input,select,button{{padding:9px 11px;border-radius:8px;border:1px solid #40516b;background:#07101f;color:#e8f0fb}}
button{{cursor:pointer}}main{{display:grid;grid-template-columns:minmax(0,1fr) 300px;height:calc(100vh - 67px)}}
#viewport{{overflow:hidden;position:relative}}svg{{width:100%;height:100%;touch-action:none}}aside{{border-left:1px solid #24344d;padding:16px;overflow:auto;background:#0d1829}}
.node{{cursor:pointer}}.node circle{{stroke:#9fb4d1;stroke-width:1.5}}.node.selected circle{{stroke:#fff;stroke-width:3}}.node text{{fill:#e8f0fb;font-size:11px;pointer-events:none}}
.edge{{stroke:#48617f;stroke-opacity:.65;stroke-width:1.2}}.edge[data-relation="contradicts"]{{stroke:#ff6b6b;stroke-width:2.2}}.edge[data-relation="duplicate_of"]{{stroke:#c18cff;stroke-dasharray:5 4;stroke-width:2}}
.badge{{font-size:12px;color:#9fb4d1}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media(max-width:800px){{main{{grid-template-columns:1fr}}aside{{display:none}}}}
</style></head>
<body><header><strong>Knowledge Galaxy</strong><span class="badge">Project: {project or 'all'}</span>
<input id="search" maxlength="200" placeholder="Search nodes"><select id="kind"><option value="">All types</option></select>
<button id="zoomIn">+</button><button id="zoomOut">−</button><button id="reset">Reset</button><button id="focus">Focus</button></header>
<main><div id="viewport"><svg id="graph" role="img" aria-label="Knowledge graph"><g id="scene"></g></svg></div>
<aside><h2>Selection</h2><pre id="details">Select a node</pre></aside></main>
<script>
const data={graph_json};const svg=document.getElementById('graph'),scene=document.getElementById('scene');
const search=document.getElementById('search'),kind=document.getElementById('kind'),details=document.getElementById('details');
let scale=1,tx=0,ty=0,selected=null,drag=null;const kinds=[...new Set(data.nodes.map(n=>n.kind))].sort();
for(const value of kinds){{const option=document.createElement('option');option.value=value;option.textContent=value;kind.appendChild(option)}}
const palette={{project:'#4da3ff',file:'#00b894',symbol:'#f7b731',memory:'#a55eea',decision:'#fd9644',task:'#45aaf2',warning:'#eb3b5a',session:'#778ca3'}};
const positions=new Map();const count=Math.max(data.nodes.length,1);data.nodes.forEach((n,i)=>{{const angle=i/count*Math.PI*2;const ring=130+70*(i%3);positions.set(n.id,{{x:420+Math.cos(angle)*ring,y:320+Math.sin(angle)*ring}})}});
function el(name,attrs={{}}){{const node=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));return node}}
function draw(){{scene.replaceChildren();const visible=new Set(data.nodes.filter(n=>(!kind.value||n.kind===kind.value)&&(!search.value||JSON.stringify(n).toLowerCase().includes(search.value.toLowerCase()))).map(n=>n.id));
for(const e of data.edges){{if(!visible.has(e.source)||!visible.has(e.target))continue;const a=positions.get(e.source),b=positions.get(e.target);scene.appendChild(el('line',{{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'edge','data-relation':e.relation}}))}}
for(const n of data.nodes){{if(!visible.has(n.id))continue;const p=positions.get(n.id),g=el('g',{{class:'node'+(selected===n.id?' selected':''),transform:`translate(${{p.x}} ${{p.y}})`,'data-id':n.id}});const c=el('circle',{{r:n.kind==='project'?18:11,fill:palette[n.kind]||'#8e9aaf'}});if(n.contradicted)c.setAttribute('stroke','#ff6b6b');if(n.stale)c.setAttribute('stroke-dasharray','4 3');g.append(c);const t=el('text',{{x:15,y:4}});t.textContent=n.label;g.append(t);g.addEventListener('click',()=>{{selected=n.id;details.textContent=JSON.stringify(n,null,2);draw()}});scene.append(g)}}applyTransform()}}
function applyTransform(){{scene.setAttribute('transform',`translate(${{tx}} ${{ty}}) scale(${{scale}})`)}}function zoom(f){{scale=Math.min(4,Math.max(.25,scale*f));applyTransform()}}
svg.addEventListener('pointerdown',e=>{{drag={{x:e.clientX-tx,y:e.clientY-ty}};svg.setPointerCapture(e.pointerId)}});svg.addEventListener('pointermove',e=>{{if(!drag)return;tx=e.clientX-drag.x;ty=e.clientY-drag.y;applyTransform()}});svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('wheel',e=>{{e.preventDefault();zoom(e.deltaY<0?1.1:.9)}},{{passive:false}});
search.addEventListener('input',draw);kind.addEventListener('change',draw);document.getElementById('zoomIn').onclick=()=>zoom(1.2);document.getElementById('zoomOut').onclick=()=>zoom(.8);document.getElementById('reset').onclick=()=>{{scale=1;tx=0;ty=0;selected=null;draw()}};
document.getElementById('focus').onclick=()=>{{if(!selected)return;const neighbors=new Set([selected]);for(const e of data.edges)if(e.source===selected)neighbors.add(e.target);else if(e.target===selected)neighbors.add(e.source);search.value='';kind.value='';for(const n of data.nodes){{const node=scene.querySelector(`[data-id="${{CSS.escape(n.id)}}"]`);if(node)node.style.opacity=neighbors.has(n.id)?'1':'.12'}}}};draw();
</script></body></html>'''
