#!/usr/bin/env python3
"""Turn a short game idea into a playable, self-contained browser prototype."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from project_adapter import inspect_project, stage_unreal_assets, write_import_helper
from local_game_planner import generate_local_content


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48].strip("-") or "idea-game"


def validate_game_content(game: dict) -> None:
    """Check the generated encounter against the bundled content schema's core constraints."""
    required = {"title", "theme", "setting", "objective", "player", "npc", "enemy", "collectible", "quest"}
    missing = required - game.keys()
    if missing:
        raise ValueError(f"Game content is missing required fields: {', '.join(sorted(missing))}")
    if game["theme"] not in {"sky-dragon", "dark-fantasy", "adventure"}:
        raise ValueError(f"Unsupported game theme: {game['theme']!r}")
    for key in ("title", "setting", "objective"):
        if not isinstance(game[key], str) or not game[key].strip():
            raise ValueError(f"Game content field {key!r} must be a non-empty string")
    groups = {
        "player": {"name", "role"},
        "npc": {"name", "role", "dialogue"},
        "enemy": {"name", "role", "health", "attack"},
        "collectible": {"name", "count", "color"},
        "quest": {"name", "brief", "reward"},
    }
    for group, fields in groups.items():
        if not isinstance(game[group], dict) or not fields.issubset(game[group]):
            raise ValueError(f"Game content group {group!r} is incomplete")
    enemy, collectible = game["enemy"], game["collectible"]
    if not (isinstance(enemy["health"], int) and 1 <= enemy["health"] <= 10):
        raise ValueError("Enemy health must be an integer from 1 to 10")
    if not (isinstance(enemy["attack"], int) and 1 <= enemy["attack"] <= 4):
        raise ValueError("Enemy attack must be an integer from 1 to 4")
    if not (isinstance(collectible["count"], int) and 1 <= collectible["count"] <= 8):
        raise ValueError("Collectible count must be an integer from 1 to 8")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(collectible["color"])):
        raise ValueError("Collectible color must be a six-digit hex color")


def make_project(idea: str, title: str, project_dir: Path) -> dict:
    slug = slugify(title)
    return {
        "schemaVersion": "1.0",
        "project": {
            "id": slug,
            "name": title,
            "description": idea,
            "status": "in-progress",
            "target": {
                "engine": "browser-prototype",
                "assetFormats": ["html", "json"],
                "constraints": ["Generated prototype uses procedural 2D graphics; no external assets required."]
            },
            "styleGuide": {
                "prompt": idea,
                "references": [],
                "palette": ["#10151f", "#9ed3c6", "#f1bd75"],
                "notes": "First-pass visual direction inferred from the idea; edit this manifest to refine it."
            }
        },
        "assets": [
            {
                "id": "player",
                "name": "Player character",
                "kind": "character",
                "status": "planned",
                "source": {"id": "idea-brief", "path": "project.json", "mediaType": "application/json", "format": "json"},
                "prompt": f"Design a readable player character for this game idea: {idea}",
                "requiredFormats": ["glb", "fbx", "png"],
                "stageIds": ["character-concept", "character-3d", "character-blender"],
                "outputs": []
            },
            {
                "id": "world",
                "name": "Starting area",
                "kind": "environment",
                "status": "planned",
                "source": {"id": "idea-brief", "path": "project.json", "mediaType": "application/json", "format": "json"},
                "prompt": f"Create a small playable starting area for: {idea}",
                "requiredFormats": ["blend", "fbx", "glb", "png"],
                "stageIds": ["world-layout", "world-blender", "blender-concept", "render-review", "unreal-integration"],
                "outputs": []
            }
        ],
        "stages": [
            {"id": "local-game-design", "kind": "brief", "status": "planned", "dependsOn": [], "inputs": [], "outputs": [], "qualityChecks": ["Validate generated game content against game-content.schema.json."], "worker": {"name": "Ollama local model", "execution": "local"}},
            {"id": "browser-prototype", "kind": "integration", "status": "planned", "dependsOn": ["local-game-design"], "inputs": [], "outputs": [{"id": "playable", "path": "index.html", "mediaType": "text/html", "format": "html"}], "qualityChecks": ["Open index.html without a network connection.", "Complete the NPC quest, collect items, defeat the enemy, and activate the altar."], "worker": {"name": "idea_to_game.py", "execution": "local"}},
            {"id": "character-concept", "kind": "brief", "status": "planned", "dependsOn": [], "inputs": [], "outputs": [], "qualityChecks": ["Review character concept against project style guide."], "worker": {"name": "Local procedural concept builder", "execution": "local"}},
            {"id": "character-3d", "kind": "image-to-3d", "status": "planned", "dependsOn": ["character-concept"], "inputs": [], "outputs": [], "qualityChecks": ["Review mesh from front and three-quarter views."], "worker": {"name": "Local TripoSR or Hunyuan3D-Swift", "execution": "local"}},
            {"id": "character-blender", "kind": "rig", "status": "planned", "dependsOn": ["character-3d"], "inputs": [], "outputs": [], "qualityChecks": ["Inspect, rig, animate, and export through Blender."], "worker": {"name": "Blender agent tunnel", "execution": "local"}},
            {"id": "blender-concept", "kind": "scene-build", "status": "planned", "dependsOn": ["browser-prototype"], "inputs": [], "outputs": [], "qualityChecks": ["Open the generated Blender scene and inspect its render."], "worker": {"name": "Vibe Create local Blender scene builder", "execution": "local"}},
            {"id": "render-review", "kind": "validation", "status": "planned", "dependsOn": ["blender-concept"], "inputs": [], "outputs": [], "qualityChecks": ["Review subject visibility, composition, and character face placement from the rendered PNG."], "worker": {"name": "Ollama local vision model", "execution": "local"}},
            {"id": "unreal-integration", "kind": "integration", "status": "planned", "dependsOn": ["blender-concept"], "inputs": [], "outputs": [], "qualityChecks": ["Import the FBX into Unreal Editor and verify scale, materials, collision, and scene composition."], "worker": {"name": "Unreal project adapter", "execution": "local"}},
            {"id": "world-layout", "kind": "scene-build", "status": "planned", "dependsOn": [], "inputs": [], "outputs": [], "qualityChecks": ["Check scale, navigability, and visual readability."], "worker": {"name": "Local procedural scene builder", "execution": "local"}},
            {"id": "world-blender", "kind": "lighting", "status": "planned", "dependsOn": ["world-layout"], "inputs": [], "outputs": [], "qualityChecks": ["Review Blender render and runtime scene."], "worker": {"name": "Blender agent tunnel", "execution": "local"}}
        ],
        "scenes": [{"id": "starting-area", "name": "Starting area", "status": "ready", "assetIds": ["player", "world"], "stageIds": ["browser-prototype", "world-layout", "blender-concept", "render-review", "unreal-integration"], "prompt": idea, "outputs": [{"id": "playable", "path": "index.html", "mediaType": "text/html", "format": "html"}]}],
        "deliverables": [{"id": "prototype", "name": "Playable local RPG vertical slice", "status": "complete", "stageIds": ["local-game-design", "browser-prototype"], "outputs": [{"id": "playable", "path": "index.html", "mediaType": "text/html", "format": "html"}, {"id": "game-content", "path": "game-content.json", "mediaType": "application/json", "format": "json"}], "acceptanceCriteria": ["Game opens and runs offline.", "Player can accept a quest, collect its items, defeat an enemy, and complete the quest.", "Generated NPC and quest content matches the brief."]}],
        "metadata": {"generatedAt": datetime.now(timezone.utc).isoformat(), "generator": "scripts/idea_to_game.py", "localOnly": True, "prototypeLimitations": "Playable game is a self-contained 2D RPG vertical slice. Blender creates an accompanying low-poly concept scene; rigging, full 3D gameplay, and target-engine gameplay integration remain planned."}
    }


def make_html(idea: str, title: str) -> str:
    safe_title, safe_idea = html.escape(title), html.escape(idea)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#10151f;color:#e7e5dc;font:16px system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}}main{{width:min(920px,96vw)}}h1{{margin:.2em 0}}p{{color:#bdc6c3}}canvas{{width:100%;background:#192332;border:1px solid #52646b;border-radius:12px;image-rendering:pixelated}}.help{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}}details{{margin:1rem 0;color:#bdc6c3}}details img{{display:block;max-width:min(480px,100%);max-height:480px;margin-top:.75rem;border-radius:10px}}
</style></head><body><main><h1>{safe_title}</h1><p>{safe_idea}</p><canvas id="game" width="900" height="520" aria-label="Playable game prototype"></canvas><div class="help"><span>Move: WASD / arrows</span><span>Interact: E</span><span id="status">Find the glowing objective.</span></div><details id="concept"><summary>Generated Blender concept scene</summary><img src="blender-concept/concept.png" alt="Render of the Blender concept scene" onerror="this.parentElement.hidden=true"></details></main>
<script>
const c=document.querySelector('#game'),x=c.getContext('2d'),status=document.querySelector('#status');
const keys=new Set(),player={{x:110,y:260,r:15}},goal={{x:735,y:250,r:22}},obstacles=[{{x:310,y:90,w:80,h:170}},{{x:510,y:280,w:110,h:150}}];let won=false;
addEventListener('keydown',e=>{{keys.add(e.key.toLowerCase());if(['arrowup','arrowdown','arrowleft','arrowright',' '].includes(e.key.toLowerCase()))e.preventDefault();if(e.key.toLowerCase()==='e'&&Math.hypot(player.x-goal.x,player.y-goal.y)<58){{won=true;status.textContent='Objective complete! Refresh to play again.'}}}});addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
function frame(){{if(!won){{let dx=0,dy=0;if(keys.has('a')||keys.has('arrowleft'))dx--;if(keys.has('d')||keys.has('arrowright'))dx++;if(keys.has('w')||keys.has('arrowup'))dy--;if(keys.has('s')||keys.has('arrowdown'))dy++;let n=Math.hypot(dx,dy)||1;player.x=Math.max(20,Math.min(880,player.x+dx/n*3));player.y=Math.max(20,Math.min(500,player.y+dy/n*3))}}x.clearRect(0,0,900,520);x.fillStyle='#202d39';x.fillRect(24,24,852,472);x.strokeStyle='#647b7d';x.lineWidth=3;x.strokeRect(24,24,852,472);x.fillStyle='#40525a';for(const o of obstacles)x.fillRect(o.x,o.y,o.w,o.h);x.fillStyle='#b68b52';x.beginPath();x.arc(goal.x,goal.y,goal.r+8,0,Math.PI*2);x.globalAlpha=.22;x.fill();x.globalAlpha=1;x.fillStyle='#f1bd75';x.beginPath();x.arc(goal.x,goal.y,goal.r,0,Math.PI*2);x.fill();x.fillStyle='#9ed3c6';x.beginPath();x.arc(player.x,player.y,player.r,0,Math.PI*2);x.fill();x.fillStyle='#e7e5dc';x.font='14px system-ui';x.fillText('START',70,220);x.fillText(won?'DONE':'OBJECTIVE · E',goal.x-48,goal.y+48);requestAnimationFrame(frame)}}frame();
</script></body></html>'''


def make_rpg_html(game: dict, planner_source: str) -> str:
    """Build an offline top-down RPG using only bundled HTML/CSS/canvas code."""
    encoded = json.dumps(game, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    page = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#111820"><title>__TITLE__</title>
<style>
:root{color-scheme:dark;--ink:#ede8d9;--muted:#a9b3b2;--gold:#edbd67;--panel:#17232b;--line:#3d5158}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 50% 0%,#283843,#10161d 65%);color:var(--ink);font:15px/1.45 ui-serif,Georgia,serif;min-height:100vh;display:grid;place-items:center;padding:22px}main{width:min(1100px,100%)}header{display:flex;justify-content:space-between;align-items:end;gap:1rem;margin:0 0 12px}h1{font-size:clamp(24px,4vw,38px);letter-spacing:.04em;margin:0;color:#f4dfb4}header p{margin:3px 0 0;color:var(--muted)}.badge{border:1px solid #526367;color:#b4d1c6;padding:5px 10px;border-radius:999px;font:11px/1.2 system-ui;text-transform:uppercase;letter-spacing:.1em;white-space:nowrap}.layout{display:grid;grid-template-columns:minmax(0,1fr) 245px;gap:12px}.frame{background:#111a20;border:1px solid #56676a;padding:7px;border-radius:8px;box-shadow:0 24px 70px #0008}canvas{display:block;width:100%;height:auto;aspect-ratio:8/5;background:#293d3b;image-rendering:pixelated;border-radius:3px}.side{background:linear-gradient(155deg,#1d2a31,#131c22);border:1px solid var(--line);border-radius:8px;padding:15px}.side h2{font-size:15px;color:var(--gold);margin:0 0 6px}.side p{color:#c0c9c4;margin:0 0 13px}.meter{height:7px;background:#2e3b3d;border-radius:99px;overflow:hidden;margin:5px 0 12px}.meter i{display:block;height:100%;background:linear-gradient(90deg,#9c473f,#e67b59);width:100%;transition:width .2s}.quest{border-top:1px solid #34464a;padding-top:13px;margin-top:12px}.quest strong{display:block;color:#f1dfbb;margin-bottom:4px}.hint{font:12px/1.5 system-ui;color:#aebbb8;border-top:1px solid #34464a;padding-top:12px;margin-top:13px}.toast{min-height:46px;color:#eed6a3;font:13px/1.4 system-ui;margin-top:12px}.controls{display:flex;gap:8px;flex-wrap:wrap;color:#aebbb8;font:11px system-ui;margin-top:9px}.controls span{border:1px solid #3e5155;border-radius:4px;padding:4px 7px}.concepts{margin-top:14px;color:#d8d3c6}.renders{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}.renders figure{margin:10px 0;flex:1 1 320px}.renders figcaption{font:12px system-ui;color:#aebbb8;margin-bottom:5px}.renders img{display:block;width:100%;height:auto;border:1px solid #3d5158;border-radius:5px}.footer{color:#718184;font:10px system-ui;text-align:right;margin-top:9px}@media(max-width:760px){body{padding:10px}.layout{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.side .quest,.side .hint{grid-column:1/-1}.badge{display:none}}
</style></head><body><main><header><div><h1>__TITLE__</h1><p id="setting"></p></div><span class="badge">Local-only build · __PLANNER__</span></header><div class="layout"><div><div class="frame"><canvas id="game" width="960" height="600" aria-label="Playable top-down RPG"></canvas></div><div class="controls"><span>WASD / arrows: move</span><span>E: talk / interact</span><span>Space: attack</span><span>Esc: pause</span></div><div class="toast" id="toast" role="status">Find the guide to begin the quest.</div></div><aside class="side"><h2 id="player-name"></h2><p id="player-role"></p><div>Health <span id="health-text">100 / 100</span></div><div class="meter"><i id="health-bar"></i></div><div>Inventory <span id="inventory">empty</span></div><div class="quest"><strong id="quest-name"></strong><p id="quest-brief"></p><p>Progress: <span id="progress">0</span></p></div><div class="hint"><b>Nearby character</b><br><span id="npc-card"></span><br><br><b>Objective</b><br><span id="objective"></span></div></aside></div><details class="concepts"><summary>Blender renders · scene and character close-up</summary><div class="renders"><figure><figcaption>Full concept scene</figcaption><img src="blender-concept/concept.png" alt="Render of the Blender concept scene" onerror="this.closest('figure').hidden=true"></figure><figure><figcaption>Character face close-up</figcaption><img src="blender-concept/character-closeup.png" alt="Close-up render for reviewing the character's face" onerror="this.closest('figure').hidden=true"></figure></div></details><div class="footer">Generated locally with __PLANNER__. No network requests from this game.</div></main>
<script>
'use strict';
const D=__GAME_DATA__;
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
const ui={toast:document.getElementById('toast'),health:document.getElementById('health-text'),bar:document.getElementById('health-bar'),inventory:document.getElementById('inventory'),progress:document.getElementById('progress')};
document.getElementById('setting').textContent=D.setting;
document.getElementById('player-name').textContent=D.player.name;
document.getElementById('player-role').textContent=D.player.role;
document.getElementById('quest-name').textContent=D.quest.name;
document.getElementById('quest-brief').textContent=D.quest.brief;
document.getElementById('npc-card').textContent=D.npc.name+' · '+D.npc.role;
document.getElementById('objective').textContent=D.objective;
const keys=new Set(),player={x:112,y:390,r:17,hp:100,maxHp:100,faceX:1,faceY:0,swing:0,attackCooldown:0,invulnerable:0};
const npc={x:160,y:305};
const enemy={x:765,y:347,hp:D.enemy.health,maxHp:D.enemy.health,attackCooldown:0,alive:true};
const shrine={x:835,y:140};
const shards=[{x:350,y:173,got:false,phase:0},{x:489,y:440,got:false,phase:1.8},{x:665,y:189,got:false,phase:3.1},{x:205,y:490,got:false,phase:.9},{x:764,y:90,got:false,phase:2.4},{x:555,y:108,got:false,phase:3.8},{x:804,y:474,got:false,phase:4.7},{x:187,y:120,got:false,phase:5.3}].slice(0,D.collectible.count);
const walls=[{x:273,y:78,w:34,h:178},{x:473,y:257,w:142,h:28},{x:650,y:70,w:34,h:127},{x:365,y:365,w:36,h:150},{x:55,y:230,w:67,h:24}];
let active=false,complete=false,paused=false,toastTimer=0,damageFlash=0;
const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
function say(text){ui.toast.textContent=text;toastTimer=300}
function blocked(x,y){if(x<30||x>930||y<35||y>570)return true;return walls.some(o=>x>o.x-13&&x<o.x+o.w+13&&y>o.y-13&&y<o.y+o.h+13)}
addEventListener('keydown',e=>{const k=e.key.toLowerCase();if(['arrowup','arrowdown','arrowleft','arrowright',' '].includes(k))e.preventDefault();keys.add(k);if(k==='escape')paused=!paused;if(k==='e'&&!e.repeat)interact();if(k===' '&&!e.repeat)attack()});
addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
function interact(){if(paused)return;if(dist(player,npc)<62){if(!active){active=true;say(D.npc.name+': “'+D.npc.dialogue+'” Quest: '+D.objective)}else if(complete)say(D.npc.name+': “'+D.quest.reward+'.”');else say(D.objective);return}if(dist(player,shrine)<67){if(complete){say('Quest complete — '+D.quest.reward+'.');}else if(active&&shards.every(s=>s.got)&&!enemy.alive){complete=true;say('Quest complete — '+D.quest.reward+'.')}else if(!active)say('The altar is cold. Speak with '+D.npc.name+' first.');else say('The altar waits: gather '+D.collectible.count+' '+D.collectible.name+(D.collectible.count===1?'':'s')+' and defeat the '+D.enemy.name+'.');return}say('Nothing to interact with nearby. Find '+D.npc.name+'.')}
function attack(){if(!active||complete||!enemy.alive||player.attackCooldown>0||dist(player,enemy)>93)return;enemy.hp=Math.max(0,enemy.hp-1);player.attackCooldown=24;player.swing=12;if(enemy.hp===0){enemy.alive=false;say('The '+D.enemy.name+' falls. Return to the altar when your collection is complete.')}else say('Strike! '+D.enemy.name+' health: '+enemy.hp+'/'+enemy.maxHp)}
function update(){if(paused||complete)return;let dx=0,dy=0;if(keys.has('w')||keys.has('arrowup'))dy--;if(keys.has('s')||keys.has('arrowdown'))dy++;if(keys.has('a')||keys.has('arrowleft'))dx--;if(keys.has('d')||keys.has('arrowright'))dx++;if(dx||dy){const n=Math.hypot(dx,dy);dx/=n;dy/=n;player.faceX=dx;player.faceY=dy;const speed=2.8;if(!blocked(player.x+dx*speed,player.y))player.x+=dx*speed;if(!blocked(player.x,player.y+dy*speed))player.y+=dy*speed}
if(active){for(const s of shards){if(!s.got&&dist(player,s)<24){s.got=true;say('Collected '+D.collectible.name+'.')}}if(enemy.alive&&dist(player,enemy)<205){const n=dist(player,enemy)||1;const ex=(player.x-enemy.x)/n,ey=(player.y-enemy.y)/n;if(n>39&&!blocked(enemy.x+ex*1.05,enemy.y))enemy.x+=ex*1.05;if(n>39&&!blocked(enemy.x,enemy.y+ey*1.05))enemy.y+=ey*1.05;if(n<40&&enemy.attackCooldown<=0&&player.invulnerable<=0){player.hp=Math.max(0,player.hp-D.enemy.attack*8);enemy.attackCooldown=56;player.invulnerable=38;damageFlash=9;say(D.enemy.name+' hits you for '+(D.enemy.attack*8)+'.');if(player.hp===0){player.hp=100;player.x=112;player.y=390;say('You recover at the trailhead. The quest remains active.')}}}}
if(player.attackCooldown>0)player.attackCooldown--;if(player.swing>0)player.swing--;if(player.invulnerable>0)player.invulnerable--;if(enemy.attackCooldown>0)enemy.attackCooldown--;if(damageFlash>0)damageFlash--;if(toastTimer>0)toastTimer--;ui.health.textContent=player.hp+' / '+player.maxHp;ui.bar.style.width=(player.hp/player.maxHp*100)+'%';const got=shards.filter(s=>s.got).length;ui.progress.textContent=got+' / '+D.collectible.count+' '+D.collectible.name+' · '+(enemy.alive?D.enemy.name+' '+enemy.hp+'/'+enemy.maxHp+' HP':D.enemy.name+' defeated');ui.inventory.textContent=got?got+' × '+D.collectible.name:'empty';}
function ground(){const dark=D.theme==='dark-fantasy',sky=D.theme==='sky-dragon';const palette=dark?['#2a302e','#343a35','#303832','#363b35']:sky?['#29383e','#34464b','#304247','#39494b']:['#344039','#3e5143','#394b3e','#405343'];ctx.fillStyle=dark?'#171f20':sky?'#1d2a31':'#202822';ctx.fillRect(0,0,960,600);ctx.fillStyle=palette[0];ctx.fillRect(26,26,908,548);for(let y=30;y<570;y+=38){for(let x=30;x<930;x+=38){const v=(x*17+y*29)%13;ctx.fillStyle=palette[v<3?1:v<7?2:3];ctx.fillRect(x,y,36,36);if(v===1){ctx.fillStyle=dark?'#474a40':sky?'#536361':'#677558';ctx.fillRect(x+9,y+11,2,2);ctx.fillRect(x+24,y+25,2,2)}}}ctx.strokeStyle='#9b865e';ctx.lineWidth=3;ctx.strokeRect(26,26,908,548);ctx.fillStyle='#c7b68f';ctx.font='14px Georgia';const worldText=D.theme==='sky-dragon'?'SKY ISLAND':dark?'WRAITHMOOR TRAIL':'THE FRONTIER';ctx.fillText(worldText,42,54);for(const w of walls){ctx.fillStyle='#13191b';ctx.fillRect(w.x+4,w.y+6,w.w,w.h);ctx.fillStyle=dark?'#555850':'#66655a';ctx.fillRect(w.x,w.y,w.w,w.h);ctx.fillStyle=dark?'#777568':'#8b8069';ctx.fillRect(w.x,w.y,w.w,5)}for(let i=0;i<8;i++){const x=65+i*113,y=(i%2?90:520);ctx.fillStyle=dark?'#202825':'#25342e';ctx.beginPath();ctx.arc(x,y,19,0,Math.PI*2);ctx.fill();ctx.fillStyle=dark?'#404941':'#52664b';ctx.beginPath();ctx.arc(x-4,y-4,15,0,Math.PI*2);ctx.fill()}ctx.fillStyle='#c3ae80';ctx.font='12px Georgia';ctx.fillText('Trailhead',53,430)}
function drawPerson(o,color,label,isPlayer=false){ctx.save();ctx.translate(o.x,o.y);if(isPlayer){const dragon=D.player.role.toLowerCase().includes('dragon');ctx.fillStyle=player.invulnerable>0?'#f1d7b0':color;if(dragon){ctx.beginPath();ctx.ellipse(-4,3,19,11,-.18,0,Math.PI*2);ctx.fill();ctx.fillStyle='#597d68';ctx.beginPath();ctx.moveTo(-15,1);ctx.lineTo(-28,-7);ctx.lineTo(-24,6);ctx.fill();ctx.fillStyle='#8bb99a';ctx.beginPath();ctx.ellipse(9,-5,9,8,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#e9d88d';ctx.beginPath();ctx.arc(12,-9,1.6,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.arc(12,-1,1.6,0,Math.PI*2);ctx.fill()}else{ctx.fillStyle='#52384a';ctx.beginPath();ctx.ellipse(0,5,15,17,0,0,Math.PI*2);ctx.fill();ctx.fillStyle=color;ctx.beginPath();ctx.arc(0,-10,8,0,Math.PI*2);ctx.fill();ctx.fillStyle='#ead39d';ctx.fillRect(3,-12,3,2)}if(player.swing>0){ctx.strokeStyle='#ffe294';ctx.lineWidth=4;ctx.beginPath();ctx.arc(0,0,48,-1.5,1.0);ctx.stroke()}}else{ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(0,5,14,16,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#dabd8a';ctx.beginPath();ctx.arc(0,-10,7,0,Math.PI*2);ctx.fill()}ctx.fillStyle='#f4e7cb';ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText(label,0,-30);ctx.restore()}
function drawEnemy(){if(!enemy.alive)return;ctx.save();ctx.translate(enemy.x,enemy.y);ctx.fillStyle='#401f27';ctx.beginPath();ctx.arc(0,0,19,0,Math.PI*2);ctx.fill();ctx.fillStyle='#b74f4d';ctx.beginPath();ctx.moveTo(-16,-5);ctx.lineTo(-21,-22);ctx.lineTo(-6,-14);ctx.lineTo(1,-25);ctx.lineTo(8,-13);ctx.lineTo(22,-19);ctx.lineTo(17,-3);ctx.lineTo(14,13);ctx.lineTo(0,20);ctx.lineTo(-14,12);ctx.closePath();ctx.fill();ctx.fillStyle='#ffdb8a';ctx.fillRect(-8,-3,4,4);ctx.fillRect(5,-3,4,4);ctx.fillStyle='#221a1d';ctx.fillRect(-18,-30,36,4);ctx.fillStyle='#d44d4b';ctx.fillRect(-18,-30,36*enemy.hp/enemy.maxHp,4);ctx.fillStyle='#f2ddd1';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText(D.enemy.name,0,-36);ctx.restore()}
function render(){ground();ctx.save();ctx.translate(shrine.x,shrine.y);ctx.fillStyle=complete?'#f2d587':'#756247';ctx.beginPath();ctx.arc(0,0,25,0,Math.PI*2);ctx.fill();ctx.strokeStyle=complete?'#fff0b3':'#be9d5f';ctx.lineWidth=3;ctx.beginPath();ctx.arc(0,0,18,0,Math.PI*2);ctx.stroke();ctx.fillStyle=complete?'#fff2b2':'#c99c4f';ctx.beginPath();ctx.moveTo(0,-12);ctx.lineTo(8,0);ctx.lineTo(0,12);ctx.lineTo(-8,0);ctx.closePath();ctx.fill();ctx.fillStyle='#eee0be';ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText('ALTAR',0,42);ctx.restore();for(const s of shards){if(s.got)continue;const bob=Math.sin(performance.now()/320+s.phase)*4;ctx.save();ctx.translate(s.x,s.y+bob);ctx.shadowColor=D.collectible.color;ctx.shadowBlur=18;ctx.fillStyle=D.collectible.color;ctx.beginPath();ctx.moveTo(0,-12);ctx.lineTo(9,0);ctx.lineTo(0,12);ctx.lineTo(-9,0);ctx.closePath();ctx.fill();ctx.restore()}drawPerson(npc,'#9d7651',D.npc.name);drawEnemy();drawPerson(player,'#789cb1',D.player.name,true);ctx.fillStyle='#e5dec8';ctx.font='12px system-ui';ctx.textAlign='left';if(!active)ctx.fillText('E · speak',npc.x-28,npc.y+37);else if(!complete)ctx.fillText('E · interact',shrine.x-30,shrine.y+47);if(damageFlash){ctx.fillStyle='rgba(175,45,45,.17)';ctx.fillRect(0,0,960,600)}if(paused){ctx.fillStyle='#071015cc';ctx.fillRect(0,0,960,600);ctx.fillStyle='#f0dfba';ctx.textAlign='center';ctx.font='38px Georgia';ctx.fillText('PAUSED',480,285);ctx.font='14px system-ui';ctx.fillText('Press Esc to return',480,320)}}
function loop(){update();render();requestAnimationFrame(loop)}loop();
</script></body></html>'''
    return (page.replace("__TITLE__", html.escape(game["title"]))
            .replace("__PLANNER__", html.escape(planner_source))
            .replace("__GAME_DATA__", encoded))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("idea", help="A sentence or two describing the game")
    parser.add_argument("--title", help="Project title (defaults to the first few words)")
    parser.add_argument("--out", type=Path, default=Path("generated-game"), help="Output directory")
    parser.add_argument("--with-blender", action="store_true", help="Also generate a local Blender concept scene")
    parser.add_argument("--blender-bin", type=Path, default=Path("/Applications/Blender.app/Contents/MacOS/Blender"), help="Blender executable")
    parser.add_argument("--target-project", type=Path, help="Optional game project folder or .uproject descriptor to inspect and integrate with")
    parser.add_argument("--model", default=os.environ.get("VIBE_GAME_MODEL", "qwen3.5:2b"), help="Installed Ollama model for local game-content planning")
    parser.add_argument("--vision-model", default=os.environ.get("VIBE_VISION_MODEL", "qwen2.5vl:3b"), help="Installed Ollama vision model for local render review")
    parser.add_argument("--skip-vision-review", action="store_true", help="Skip the optional local visual review of Blender renders")
    parser.add_argument("--open", action="store_true", help="Open the game in the default browser after generation")
    args = parser.parse_args()
    title = args.title or " ".join(args.idea.split()[:5]).strip(".,!?;:") or "Idea Game"
    target_info = None
    if args.target_project:
        try:
            target_info = inspect_project(args.target_project)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"Planning the encounter with local Ollama model {args.model} (localhost only)...")
    game_content, planner_source, planner_note = generate_local_content(args.idea, title, args.model)
    idea_lower = args.idea.lower()
    if "dragon" in idea_lower or "floating island" in idea_lower or "sky island" in idea_lower:
        game_content["theme"] = "sky-dragon"
        if "dragon" in idea_lower and "dragon" not in game_content["player"]["role"].lower():
            game_content["player"]["role"] = "young sky dragon"
    elif any(word in idea_lower for word in ("valtherion", "crypt", "wraithmoor", "murkfen", "medieval", "dark fantasy", "bog")):
        game_content["theme"] = "dark-fantasy"
        game_content["player"]["role"] = "Child of the Light"
    else:
        game_content["theme"] = "adventure"
    if game_content["theme"] == "dark-fantasy" and "wisp" in game_content["collectible"]["name"].lower():
        game_content["collectible"]["color"] = "#86F1D1"
    elif game_content["theme"] == "sky-dragon" and any(
        word in game_content["collectible"]["name"].lower() for word in ("star", "shard")
    ):
        game_content["collectible"]["color"] = "#FFC65C"
    brief_lower = game_content["quest"]["brief"].lower()
    objective = game_content["quest"]["brief"].rstrip(" .")
    collectible_name = game_content["collectible"]["name"]
    collectible_plural = collectible_name if collectible_name.lower().endswith("s") else collectible_name + "s"
    if collectible_name.lower() not in brief_lower:
        objective += f". Gather {game_content['collectible']['count']} {collectible_plural}"
    if game_content["enemy"]["name"].lower() not in brief_lower or not any(word in brief_lower for word in ("defeat", "destroy", "kill", "slay", "vanquish")):
        objective += f". Defeat {game_content['enemy']['name']}"
    game_content["objective"] = objective.rstrip(" .") + ". Return to the altar and interact to complete the quest."
    validate_game_content(game_content)
    project = make_project(args.idea, title, args.out)
    if target_info:
        project["project"]["target"] = {
            "engine": target_info["engine"],
            "assetFormats": ["blend", "fbx", "png"],
            "constraints": ["Existing project files are inspected before integration.", "Unreal assets are staged under Content/VibeCreate/<project-id>."]
        }
        project["metadata"]["targetProject"] = target_info
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "game-content.json").write_text(json.dumps(game_content, ensure_ascii=False, indent=2) + "\n")
    (args.out / "planner.log").write_text(f"source: {planner_source}\n{planner_note}\n")
    design_stage = next(stage for stage in project["stages"] if stage["id"] == "local-game-design")
    design_stage["status"] = "passed"
    design_stage["worker"]["name"] = planner_source
    design_stage["outputs"] = [{"id": "game-content", "path": "game-content.json", "mediaType": "application/json", "format": "json"}]
    browser_stage = next(stage for stage in project["stages"] if stage["id"] == "browser-prototype")
    browser_stage["status"] = "passed"
    browser_stage["inputs"] = [{"id": "game-content", "path": "game-content.json", "mediaType": "application/json", "format": "json"}]
    project["metadata"]["contentPlanner"] = planner_source
    project["metadata"]["plannerNote"] = planner_note
    project["metadata"]["gameContentValidation"] = "passed against schemas/game-content.schema.json core constraints"
    (args.out / "project.json").write_text(json.dumps(project, indent=2) + "\n")
    (args.out / "index.html").write_text(make_rpg_html(game_content, planner_source))
    print(f"Created {args.out / 'index.html'} (offline playable RPG slice)")
    print(f"Created {args.out / 'game-content.json'} using {planner_source}")
    print(f"Created {args.out / 'project.json'} (asset pipeline manifest)")
    if args.with_blender:
        if not args.blender_bin.is_file():
            parser.error(f"Blender executable not found: {args.blender_bin}")
        blend_dir = args.out / "blender-concept"
        blend_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({"VIBE_GAME_TITLE": title, "VIBE_GAME_IDEA": args.idea,
                    "VIBE_GAME_CONTENT": str((args.out / "game-content.json").resolve()),
                    "VIBE_GAME_THEME": game_content["theme"],
                    "VIBE_GAME_OUTDIR": str(blend_dir.resolve())})
        builder = Path(__file__).with_name("generate_blender_concept.py")
        print("Building the local low-poly Blender concept scene...")
        with (blend_dir / "blender.log").open("w") as log:
            result = subprocess.run([str(args.blender_bin), "--background", "--python", str(builder)],
                                    env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        manifest = json.loads((args.out / "project.json").read_text())
        scene_stage = next(stage for stage in manifest["stages"] if stage["id"] == "blender-concept")
        concept_asset = next(asset for asset in manifest["assets"] if asset["id"] == "world")
        if result.returncode == 0 and all((blend_dir / name).is_file() for name in ("concept.blend", "concept.png", "character-closeup.png", "concept.fbx")):
            scene_stage["status"] = "review"
            scene_stage["outputs"] = [
                {"id": "concept-blend", "path": "blender-concept/concept.blend", "mediaType": "application/x-blender", "format": "blend"},
                {"id": "concept-render", "path": "blender-concept/concept.png", "mediaType": "image/png", "format": "png"},
                {"id": "character-closeup", "path": "blender-concept/character-closeup.png", "mediaType": "image/png", "format": "png"},
                {"id": "concept-fbx", "path": "blender-concept/concept.fbx", "mediaType": "application/vnd.autodesk.fbx", "format": "fbx"}
            ]
            concept_asset["status"] = "review"
            concept_asset["outputs"] = scene_stage["outputs"]
            manifest["metadata"]["blenderConceptStatus"] = "generated; awaiting visual review"
            print(f"Blender scene and preview created in {blend_dir}")
            review_path = args.out / "vision-review.json"
            review_stage = next(stage for stage in manifest["stages"] if stage["id"] == "render-review")
            if args.skip_vision_review:
                review_data = {"status": "skipped", "reason": "Skipped by user in the workbench", "automatedChanges": False}
                review_path.write_text(json.dumps(review_data, indent=2) + "\n")
                (args.out / "vision-review.log").write_text("Local render review skipped by user.\n")
                review_stage["status"] = "planned"
                manifest["metadata"]["blenderConceptStatus"] = "generated; local visual review skipped"
                manifest["metadata"]["visualReview"] = review_data
                print("Local visual review skipped by user.")
            else:
                review_script = Path(__file__).with_name("local_visual_review.py")
                with (args.out / "vision-review.log").open("w") as review_log:
                    review_run = subprocess.run([sys.executable, str(review_script), str(blend_dir / "concept.png"),
                                                 title, str(review_path), "--closeup", str(blend_dir / "character-closeup.png"),
                                                 "--model", args.vision_model],
                                                stdout=review_log, stderr=subprocess.STDOUT, check=False)
                if review_run.returncode == 0 and review_path.is_file():
                    review_data = json.loads(review_path.read_text())
                    review_stage["status"] = "review" if review_data.get("status") == "reviewed" else "blocked"
                    manifest["metadata"]["blenderConceptStatus"] = (
                        "generated; advisory local visual review complete"
                        if review_data.get("status") == "reviewed"
                        else "generated; local visual review unavailable"
                    )
                    review_stage["inputs"] = [
                        {"id": "concept-render", "path": "blender-concept/concept.png", "mediaType": "image/png", "format": "png"},
                        {"id": "character-closeup", "path": "blender-concept/character-closeup.png", "mediaType": "image/png", "format": "png"}
                    ]
                    review_stage["outputs"] = [{"id": "vision-review", "path": "vision-review.json", "mediaType": "application/json", "format": "json"}]
                    manifest["metadata"]["visualReview"] = review_data
                    print(f"Local visual review: {review_data.get('status')} ({review_data.get('reviewer')})")
                else:
                    review_stage["status"] = "blocked"
                    print("Local visual review could not run; see vision-review.log")
        else:
            scene_stage["status"] = "failed"
            next(stage for stage in manifest["stages"] if stage["id"] == "render-review")["status"] = "blocked"
            manifest["metadata"]["blenderConceptStatus"] = f"generation failed (exit {result.returncode}); see blender-concept/blender.log"
            print("Blender generation failed; the playable browser prototype is still available.")
        if target_info:
            adapter_stage = next(stage for stage in manifest["stages"] if stage["id"] == "unreal-integration")
            integration_dir = args.out / "unreal-integration"
            integration_dir.mkdir(parents=True, exist_ok=True)
            if target_info["engine"] == "unreal" and scene_stage["status"] == "review":
                bundle = integration_dir / "assets"
                bundle.mkdir(exist_ok=True)
                shutil.copy2(blend_dir / "concept.fbx", bundle / "concept.fbx")
                shutil.copy2(blend_dir / "concept.png", bundle / "concept.png")
                helper = write_import_helper(integration_dir, title, bundle, slugify(title))
                integration = stage_unreal_assets(target_info, blend_dir, slugify(title))
                integration["importHelper"] = str(helper.relative_to(args.out))
                (integration_dir / "integration-report.json").write_text(json.dumps(integration, indent=2) + "\n")
                adapter_stage["status"] = "review"
                adapter_stage["outputs"] = [
                    {"id": "unreal-fbx", "path": "unreal-integration/assets/concept.fbx", "mediaType": "application/vnd.autodesk.fbx", "format": "fbx"},
                    {"id": "unreal-import-helper", "path": "unreal-integration/import_into_unreal.py", "mediaType": "text/x-python", "format": "py"},
                    {"id": "unreal-integration-report", "path": "unreal-integration/integration-report.json", "mediaType": "application/json", "format": "json"}
                ]
                manifest["metadata"]["targetIntegration"] = integration
                print(f"Staged FBX assets in Unreal Content: {integration['destination']}")
            elif target_info["engine"] == "unreal":
                adapter_stage["status"] = "blocked"
                report = {"status": "blocked", "detectedEngine": "unreal",
                          "projectRoot": target_info["projectRoot"],
                          "message": "The Unreal project was recognized, but Blender did not produce the FBX bundle. See blender-concept/blender.log.",
                          "evidence": target_info["evidence"]}
                (integration_dir / "integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
                manifest["metadata"]["targetIntegration"] = report
                print("Unreal project recognized, but Blender assets were unavailable; no project files were changed.")
            else:
                adapter_stage["status"] = "blocked"
                report = {"status": "blocked", "detectedEngine": target_info["engine"],
                          "projectRoot": target_info["projectRoot"],
                          "message": "No Unreal .uproject was found. The source was inspected but left unchanged; the Blender FBX remains available in blender-concept/.",
                          "evidence": target_info["evidence"]}
                (integration_dir / "integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
                manifest["metadata"]["targetIntegration"] = report
                print(f"Project inspected ({target_info['engine']}); no Unreal project detected, so no project files were changed.")
        (args.out / "project.json").write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        print("Blender stages remain planned. Re-run with --with-blender to generate the concept scene.")
    if args.open:
        subprocess.run(["open", str((args.out / "index.html").resolve())], check=False)


if __name__ == "__main__":
    main()
