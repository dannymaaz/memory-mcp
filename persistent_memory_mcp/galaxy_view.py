"""Dependency-free browser renderer for bounded knowledge and operational graphs."""

from __future__ import annotations

import html
import json
from typing import Any, Mapping


def render_galaxy_view(graph: Mapping[str, Any], *, project_id: str | None = None) -> str:
    """Render an escaped, self-contained SVG galaxy view."""
    graph_json = json.dumps(graph, ensure_ascii=False, default=str).replace("<", "\\u003c")
    project = html.escape(project_id or "all", quote=True)
    operational = any(
        isinstance(node, Mapping) and ("risk" in node or "verification_state" in node)
        for node in graph.get("nodes", [])
    )
    title = "Operational Galaxy" if operational else "Knowledge Galaxy"
    title_html = html.escape(title)
    mode = "operational" if operational else "knowledge"
    template = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#07101f;color:#e8f0fb}
header{display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #24344d;background:#0d1829}
input,select,button{padding:8px 10px;border-radius:8px;border:1px solid #40516b;background:#07101f;color:#e8f0fb}button{cursor:pointer}
label.toggle{display:flex;gap:6px;align-items:center;padding:6px 8px;border:1px solid #40516b;border-radius:8px;font-size:12px;color:#c8d5e8}label.toggle input{padding:0}
main{display:grid;grid-template-columns:minmax(0,1fr) 310px;height:calc(100vh - 62px)}#viewport{overflow:hidden;position:relative}
svg{width:100%;height:100%;touch-action:none;background:radial-gradient(circle at center,#10213a 0,#07101f 62%)}
aside{border-left:1px solid #24344d;padding:16px;overflow:auto;background:#0d1829}.node{cursor:grab}.node.dragging{cursor:grabbing}
.node circle{stroke:#9fb4d1;stroke-width:1.5}.node.selected circle{stroke:#fff;stroke-width:3}.node text{fill:#e8f0fb;font-size:11px;pointer-events:none}
.node[data-risk="critical"] circle{stroke:#ff4d6d;stroke-width:3}.node[data-risk="high"] circle{stroke:#ff9f43;stroke-width:2.5}.node[data-risk="medium"] circle{stroke:#ffd166;stroke-width:2}
.node[data-verification="stale"] circle{stroke-dasharray:4 3}.node[data-verification="contradicted"] circle{stroke:#ff4d6d;stroke-width:3}.node[data-verification="missing_source"] circle{stroke-dasharray:2 2}.node[data-changed="true"] text{font-weight:700}
.edge{stroke:#48617f;stroke-opacity:.65;stroke-width:1.2}.edge[data-relation="contradicts"],.edge[data-verification="contradicted"]{stroke:#ff6b6b;stroke-width:2.2}.edge[data-relation="duplicate_of"]{stroke:#c18cff;stroke-dasharray:5 4;stroke-width:2}.edge[data-verification="stale"]{stroke-dasharray:4 3}
.badge{font-size:12px;color:#9fb4d1}.legend{display:grid;grid-template-columns:1fr 1fr;gap:7px;font-size:12px}.legend span::before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:var(--swatch)}
.state-list{display:grid;gap:6px;font-size:12px}.state-list span{padding:6px 8px;border:1px solid #2f405b;border-radius:7px}.state-list strong{float:right}
#minimap{position:absolute;right:14px;bottom:14px;width:180px;height:120px;border:1px solid #40516b;border-radius:8px;background:#0a1526;opacity:.92}
#status{position:absolute;left:14px;bottom:14px;padding:6px 9px;border-radius:7px;background:#0d1829;border:1px solid #24344d;font-size:12px;color:#9fb4d1}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.toolbar-group{display:flex;gap:6px}.muted{color:#9fb4d1;font-size:12px}.operational-control[hidden]{display:none}
@media(max-width:850px){main{grid-template-columns:1fr}aside{display:none}#minimap{width:140px;height:90px}}
</style></head>
<body><header><strong>__TITLE__</strong><span class="badge">Project: __PROJECT__</span>
<input id="search" maxlength="200" placeholder="Search nodes" aria-label="Search nodes"><select id="kind" aria-label="Filter by type"><option value="">All types</option></select>
<select id="risk" class="operational-control" aria-label="Filter by risk"><option value="">All risks</option></select>
<select id="verification" class="operational-control" aria-label="Filter by verification"><option value="">All verification states</option></select>
<label class="toggle operational-control" id="changedWrap"><input id="changedOnly" type="checkbox">Changed only</label>
<div class="toolbar-group"><button id="zoomIn" title="Zoom in">+</button><button id="zoomOut" title="Zoom out">−</button><button id="reset">Reset</button><button id="fit">Fit</button></div>
<div class="toolbar-group"><button id="layout">Relayout</button><button id="focus">Focus</button><button id="clearFocus">Clear focus</button></div>
<div class="toolbar-group"><button id="exportSvg">Export SVG</button><button id="exportPng">Export PNG</button></div></header>
<main><div id="viewport"><svg id="graph" role="img" aria-label="__TITLE__ graph"><g id="scene"></g></svg><canvas id="minimap" width="360" height="240" aria-label="Graph minimap"></canvas><div id="status"></div></div>
<aside><h2>Selection</h2><pre id="details">Select a node</pre><h3>Legend</h3><div id="legend" class="legend"></div><div id="operationalSummary" class="operational-control"><h3>Operational state</h3><div id="stateList" class="state-list"></div></div><p class="muted">Drag nodes to pin them. Layout and viewport are saved locally for this project.</p></aside></main>
<script>
const data=__GRAPH_JSON__;const mode='__MODE__';const operational=mode==='operational';
const svg=document.getElementById('graph'),scene=document.getElementById('scene'),viewport=document.getElementById('viewport');
const search=document.getElementById('search'),kind=document.getElementById('kind'),risk=document.getElementById('risk'),verification=document.getElementById('verification'),changedOnly=document.getElementById('changedOnly'),details=document.getElementById('details'),status=document.getElementById('status');
const minimap=document.getElementById('minimap'),mctx=minimap.getContext('2d');
let scale=1,tx=0,ty=0,selected=null,pan=null,nodeDrag=null,focusSet=null,animation=null;
const palette={project:'#4da3ff',repository:'#6c8cff',file:'#00b894',symbol:'#f7b731',memory:'#a55eea',decision:'#fd9644',task:'#45aaf2',warning:'#eb3b5a',session:'#778ca3',test:'#26de81',deployment:'#a5b1c2'};
const riskPalette={critical:'#ff4d6d',high:'#ff9f43',medium:'#ffd166',low:'#7bdff2',none:'#8e9aaf'};
const storageKey='memory-mcp-galaxy:'+String('__PROJECT__')+':'+mode;
const nodeById=new Map(data.nodes.map(n=>[n.id,n]));const positions=new Map();const velocities=new Map();const pinned=new Set();
const kinds=[...new Set(data.nodes.map(n=>n.kind).filter(Boolean))].sort();for(const value of kinds){const option=document.createElement('option');option.value=value;option.textContent=value;kind.appendChild(option)}
for(const value of kinds){const item=document.createElement('span');item.style.setProperty('--swatch',palette[value]||'#8e9aaf');item.textContent=value;document.getElementById('legend').appendChild(item)}
const risks=[...new Set(data.nodes.map(n=>n.risk).filter(Boolean))].sort((a,b)=>['critical','high','medium','low','none'].indexOf(a)-['critical','high','medium','low','none'].indexOf(b));
const verifications=[...new Set(data.nodes.map(n=>n.verification_state).filter(Boolean))].sort();
for(const value of risks){const option=document.createElement('option');option.value=value;option.textContent=value;risk.appendChild(option)}
for(const value of verifications){const option=document.createElement('option');option.value=value;option.textContent=value;verification.appendChild(option)}
if(!operational){for(const element of document.querySelectorAll('.operational-control'))element.hidden=true}else{const stateList=document.getElementById('stateList');const summary=data.summary||{};const entries=[['changed',summary.changed_nodes||0],['missing evidence',summary.missing_evidence_nodes||0],['critical',(summary.risk||{}).critical||0],['high risk',(summary.risk||{}).high||0],['stale',(summary.verification||{}).stale||0],['contradicted',(summary.verification||{}).contradicted||0]];for(const [label,value] of entries){const item=document.createElement('span');item.textContent=label;const strong=document.createElement('strong');strong.textContent=String(value);item.appendChild(strong);stateList.appendChild(item)}}
function initialLayout(){const count=Math.max(data.nodes.length,1);data.nodes.forEach((n,i)=>{const angle=i/count*Math.PI*2;const ring=120+55*(i%4);positions.set(n.id,{x:420+Math.cos(angle)*ring,y:320+Math.sin(angle)*ring});velocities.set(n.id,{x:0,y:0})})}
function loadState(){initialLayout();try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null');if(!saved)return;if(saved.viewport){scale=saved.viewport.scale||1;tx=saved.viewport.tx||0;ty=saved.viewport.ty||0}for(const [id,p] of Object.entries(saved.positions||{})){if(positions.has(id))positions.set(id,{x:Number(p.x)||0,y:Number(p.y)||0})}for(const id of saved.pinned||[])if(positions.has(id))pinned.add(id)}catch(_){}}
function saveState(){const saved={viewport:{scale,tx,ty},positions:Object.fromEntries(positions),pinned:[...pinned]};localStorage.setItem(storageKey,JSON.stringify(saved))}
function el(name,attrs={}){const node=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));return node}
function visibleNodes(){const q=search.value.trim().toLowerCase();return data.nodes.filter(n=>(!kind.value||n.kind===kind.value)&&(!operational||!risk.value||n.risk===risk.value)&&(!operational||!verification.value||n.verification_state===verification.value)&&(!operational||!changedOnly.checked||n.changed===true)&&(!q||JSON.stringify(n).toLowerCase().includes(q))&&(!focusSet||focusSet.has(n.id)))}
function draw(){scene.replaceChildren();const nodes=visibleNodes(),visible=new Set(nodes.map(n=>n.id));for(const e of data.edges){if(!visible.has(e.source)||!visible.has(e.target))continue;const a=positions.get(e.source),b=positions.get(e.target);scene.appendChild(el('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'edge','data-relation':e.relation,'data-verification':e.verification_state||''}))}
for(const n of nodes){const p=positions.get(n.id),g=el('g',{class:'node'+(selected===n.id?' selected':''),transform:`translate(${p.x} ${p.y})`,'data-id':n.id,'data-risk':n.risk||'','data-verification':n.verification_state||'','data-changed':String(n.changed===true),tabindex:'0','aria-label':`${n.kind}: ${n.label}${n.risk?`, risk ${n.risk}`:''}${n.verification_state?`, ${n.verification_state}`:''}`});const c=el('circle',{r:n.kind==='project'?18:n.kind==='repository'?14:11,fill:palette[n.kind]||'#8e9aaf'});if(n.contradicted)c.setAttribute('stroke','#ff6b6b');if(n.stale)c.setAttribute('stroke-dasharray','4 3');g.append(c);const t=el('text',{x:15,y:4});t.textContent=n.label;g.append(t);g.addEventListener('click',e=>{e.stopPropagation();selectNode(n.id)});g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectNode(n.id)}});g.addEventListener('pointerdown',e=>startNodeDrag(e,n.id,g));scene.append(g)}applyTransform();drawMinimap();const critical=nodes.filter(n=>n.risk==='critical').length,high=nodes.filter(n=>n.risk==='high').length;status.textContent=`${nodes.length} nodes · ${data.edges.filter(e=>visible.has(e.source)&&visible.has(e.target)).length} edges${operational?` · ${critical} critical · ${high} high`:''}${focusSet?' · focused':''}`}
function selectNode(id){selected=id;details.textContent=JSON.stringify(nodeById.get(id),null,2);draw()}
function applyTransform(){scene.setAttribute('transform',`translate(${tx} ${ty}) scale(${scale})`)}
function zoomAt(factor,cx=svg.clientWidth/2,cy=svg.clientHeight/2){const next=Math.min(4,Math.max(.2,scale*factor));const ratio=next/scale;tx=cx-(cx-tx)*ratio;ty=cy-(cy-ty)*ratio;scale=next;applyTransform();drawMinimap();saveState()}
function startNodeDrag(e,id,g){e.stopPropagation();const p=positions.get(id);nodeDrag={id,offsetX:e.clientX-(p.x*scale+tx),offsetY:e.clientY-(p.y*scale+ty)};g.classList.add('dragging');svg.setPointerCapture(e.pointerId)}
function runLayout(iterations=180){if(animation)cancelAnimationFrame(animation);let remaining=iterations;const step=()=>{const nodes=visibleNodes();const visible=new Set(nodes.map(n=>n.id));for(const n of nodes){if(pinned.has(n.id))continue;const p=positions.get(n.id),v=velocities.get(n.id);let fx=(420-p.x)*.0015,fy=(320-p.y)*.0015;for(const other of nodes){if(other.id===n.id)continue;const q=positions.get(other.id),dx=p.x-q.x,dy=p.y-q.y,d2=Math.max(100,dx*dx+dy*dy),force=850/d2;fx+=dx*force;fy+=dy*force}for(const e of data.edges){let other=null;if(e.source===n.id&&visible.has(e.target))other=e.target;else if(e.target===n.id&&visible.has(e.source))other=e.source;if(!other)continue;const q=positions.get(other),dx=q.x-p.x,dy=q.y-p.y,dist=Math.max(1,Math.hypot(dx,dy)),force=(dist-95)*.008;fx+=dx/dist*force;fy+=dy/dist*force}v.x=(v.x+fx)*.86;v.y=(v.y+fy)*.86;p.x+=v.x;p.y+=v.y}draw();remaining--;if(remaining>0)animation=requestAnimationFrame(step);else{animation=null;saveState()}};step()}
function fitView(){const nodes=visibleNodes();if(!nodes.length)return;const xs=nodes.map(n=>positions.get(n.id).x),ys=nodes.map(n=>positions.get(n.id).y);const minX=Math.min(...xs)-40,maxX=Math.max(...xs)+40,minY=Math.min(...ys)-40,maxY=Math.max(...ys)+40;const w=Math.max(1,maxX-minX),h=Math.max(1,maxY-minY);scale=Math.min(3,Math.max(.2,Math.min(svg.clientWidth/w,svg.clientHeight/h)*.9));tx=(svg.clientWidth-w*scale)/2-minX*scale;ty=(svg.clientHeight-h*scale)/2-minY*scale;applyTransform();drawMinimap();saveState()}
function focusSelection(){if(!selected)return;focusSet=new Set([selected]);for(const e of data.edges){if(e.source===selected)focusSet.add(e.target);else if(e.target===selected)focusSet.add(e.source)}draw();fitView()}
function clearFocus(){focusSet=null;draw();fitView()}
function drawMinimap(){mctx.clearRect(0,0,minimap.width,minimap.height);const nodes=visibleNodes();if(!nodes.length)return;const xs=nodes.map(n=>positions.get(n.id).x),ys=nodes.map(n=>positions.get(n.id).y);const minX=Math.min(...xs)-30,maxX=Math.max(...xs)+30,minY=Math.min(...ys)-30,maxY=Math.max(...ys)+30;const sx=minimap.width/Math.max(1,maxX-minX),sy=minimap.height/Math.max(1,maxY-minY),s=Math.min(sx,sy);mctx.strokeStyle='#48617f';mctx.globalAlpha=.55;for(const e of data.edges){const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)continue;mctx.beginPath();mctx.moveTo((a.x-minX)*s,(a.y-minY)*s);mctx.lineTo((b.x-minX)*s,(b.y-minY)*s);mctx.stroke()}mctx.globalAlpha=1;for(const n of nodes){const p=positions.get(n.id);mctx.fillStyle=operational&&(n.risk==='critical'||n.risk==='high')?riskPalette[n.risk]:(palette[n.kind]||'#8e9aaf');mctx.beginPath();mctx.arc((p.x-minX)*s,(p.y-minY)*s,n.id===selected?4:2.5,0,Math.PI*2);mctx.fill()}const left=(-tx/scale-minX)*s,top=(-ty/scale-minY)*s,width=svg.clientWidth/scale*s,height=svg.clientHeight/scale*s;mctx.strokeStyle='#ffffff';mctx.strokeRect(left,top,width,height)}
function download(name,type,content){const a=document.createElement('a');a.download=name;a.href=URL.createObjectURL(new Blob([content],{type}));a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function exportSvg(){const clone=svg.cloneNode(true);clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('viewBox',`0 0 ${svg.clientWidth} ${svg.clientHeight}`);download(operational?'operational-galaxy.svg':'knowledge-galaxy.svg','image/svg+xml',new XMLSerializer().serializeToString(clone))}
function exportPng(){const clone=svg.cloneNode(true);clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width',svg.clientWidth);clone.setAttribute('height',svg.clientHeight);const source=new XMLSerializer().serializeToString(clone),img=new Image(),url=URL.createObjectURL(new Blob([source],{type:'image/svg+xml'}));img.onload=()=>{const canvas=document.createElement('canvas');canvas.width=Math.max(1,svg.clientWidth*2);canvas.height=Math.max(1,svg.clientHeight*2);const ctx=canvas.getContext('2d');ctx.scale(2,2);ctx.fillStyle='#07101f';ctx.fillRect(0,0,svg.clientWidth,svg.clientHeight);ctx.drawImage(img,0,0);URL.revokeObjectURL(url);canvas.toBlob(blob=>{if(!blob)return;const a=document.createElement('a');a.download=operational?'operational-galaxy.png':'knowledge-galaxy.png';a.href=URL.createObjectURL(blob);a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)},'image/png')};img.src=url}
svg.addEventListener('pointerdown',e=>{if(e.target.closest('.node'))return;pan={x:e.clientX-tx,y:e.clientY-ty};svg.setPointerCapture(e.pointerId)});svg.addEventListener('pointermove',e=>{if(nodeDrag){const p=positions.get(nodeDrag.id);p.x=(e.clientX-nodeDrag.offsetX-tx)/scale;p.y=(e.clientY-nodeDrag.offsetY-ty)/scale;pinned.add(nodeDrag.id);draw();return}if(!pan)return;tx=e.clientX-pan.x;ty=e.clientY-pan.y;applyTransform();drawMinimap()});svg.addEventListener('pointerup',()=>{pan=null;if(nodeDrag){nodeDrag=null;saveState()}});svg.addEventListener('pointercancel',()=>{pan=null;nodeDrag=null});svg.addEventListener('wheel',e=>{e.preventDefault();zoomAt(e.deltaY<0?1.1:.9,e.offsetX,e.offsetY)},{passive:false});svg.addEventListener('click',()=>{selected=null;details.textContent='Select a node';draw()});
for(const control of [search,kind,risk,verification,changedOnly]){control.addEventListener(control===changedOnly?'change':'input',draw);if(control.tagName==='SELECT')control.addEventListener('change',draw)}document.getElementById('zoomIn').onclick=()=>zoomAt(1.2);document.getElementById('zoomOut').onclick=()=>zoomAt(.8);document.getElementById('reset').onclick=()=>{localStorage.removeItem(storageKey);scale=1;tx=0;ty=0;selected=null;focusSet=null;pinned.clear();initialLayout();draw();runLayout(120)};document.getElementById('fit').onclick=fitView;document.getElementById('layout').onclick=()=>{pinned.clear();runLayout()};document.getElementById('focus').onclick=focusSelection;document.getElementById('clearFocus').onclick=clearFocus;document.getElementById('exportSvg').onclick=exportSvg;document.getElementById('exportPng').onclick=exportPng;
window.addEventListener('resize',()=>{drawMinimap()});loadState();draw();if(!localStorage.getItem(storageKey))runLayout(140);else fitView();
</script></body></html>'''
    return (
        template.replace("__GRAPH_JSON__", graph_json)
        .replace("__PROJECT__", project)
        .replace("__TITLE__", title_html)
        .replace("__MODE__", mode)
    )
