'use strict';

const state = {projects: [], selected: null, view: 'create', jobId: null, pollTimer: null, projectById: new Map()};
const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const byId = id => document.getElementById(id);

function toast(message, isError = false) {
  const node = byId('toast');
  node.textContent = message;
  node.classList.toggle('error', isError);
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 3600);
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let value = {};
  try { value = await response.json(); } catch (_) { /* response may have no JSON body */ }
  if (!response.ok) throw new Error(value.error || `Local workbench error (${response.status})`);
  return value;
}

function post(url, body) {
  return request(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
}

function setView(name) {
  state.view = name;
  $$('.view').forEach(view => view.classList.toggle('active', view.id === `view-${name}`));
  $$('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  byId('breadcrumb-page').textContent = ({create: 'NEW GAME', projects: 'PROJECTS', pipeline: 'PIPELINE'})[name] || name.toUpperCase();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function setTool(dotId, labelId, online, label) {
  byId(dotId).classList.toggle('online', online);
  byId(dotId).classList.toggle('offline', !online);
  byId(labelId).textContent = label;
}

function fillModels(select, models, preferred) {
  const choices = models.length ? models : [preferred];
  select.replaceChildren();
  for (const model of choices) {
    const option = document.createElement('option');
    option.value = model;
    option.textContent = model;
    select.append(option);
  }
  select.value = choices.includes(preferred) ? preferred : choices[0];
}

async function loadStatus() {
  try {
    const data = await request('/api/status');
    const models = data.ollama.models || [];
    fillModels(byId('planner-model'), models.filter(name => !name.toLowerCase().includes('embed') && !name.toLowerCase().includes('vl')), data.ollama.planner);
    const visionModels = models.filter(name => name.toLowerCase().includes('vl'));
    fillModels(byId('vision-model'), visionModels.length ? visionModels : [data.ollama.vision], data.ollama.vision);
    setTool('ollama-dot', 'ollama-label', data.ollama.running, data.ollama.running ? `${models.length} MODELS` : 'OFFLINE');
    setTool('blender-dot', 'blender-label', data.blender.available, data.blender.available ? 'READY' : 'MISSING');
    setTool('godot-dot', 'godot-label', data.godot?.available, data.godot?.available ? 'READY' : 'MISSING');
    byId('godot-note').textContent = data.godot?.available
      ? 'Godot is ready. Generated projects run locally from this workbench.'
      : 'Godot 4.3+ launches the game. The workbench can still review the generated world and art sheets without it.';
    if (!data.ollama.running) {
      toast('Ollama is not running. The generator can use its local fallback planner until you start it.', true);
    }
    if (!data.blender.available) {
      byId('with-blender').checked = false;
      byId('with-blender').disabled = true;
    }
    syncGenerationMode();
  } catch (error) {
    setTool('ollama-dot', 'ollama-label', false, 'UNAVAILABLE');
    setTool('blender-dot', 'blender-label', false, 'CHECK FAILED');
    setTool('godot-dot', 'godot-label', false, 'CHECK FAILED');
    toast(error.message, true);
  }
}

function syncGenerationMode() {
  const mode = byId('game-mode').value;
  const sandbox = mode === 'sandbox';
  const darkFantasy = mode === 'dark-fantasy';
  $$('.sandbox-only-options').forEach(node => node.classList.toggle('hidden', !sandbox));
  $$('.sandbox-options').forEach(node => node.classList.toggle('hidden', !(sandbox || darkFantasy)));
  $$('.quest-options').forEach(node => node.classList.toggle('hidden', sandbox || darkFantasy));
  const isReviewAvailable = (sandbox || darkFantasy) || byId('with-blender').checked && !byId('with-blender').disabled;
  byId('with-review').disabled = !isReviewAvailable;
  byId('with-review').closest('.check-row').classList.toggle('disabled', !isReviewAvailable);
  byId('review-label').textContent = (sandbox || darkFantasy) ? 'Review pixel art / renders with local vision' : 'Review renders with local vision';
  byId('review-description').textContent = sandbox
    ? 'Advisory feedback on tile readability and sprite frames'
    : darkFantasy
    ? 'Advisory feedback on item and monster renders'
    : 'Advisory visual report; it never changes the scene';
  byId('idea-hint').textContent = sandbox
    ? 'LOCAL MODEL SHAPES THE WORLD BRIEF AND ENEMY'
    : darkFantasy
    ? 'LOCAL MODEL SHAPES THE HERO, CLASS, AND AREAS'
    : 'LOCAL MODEL WILL EXPAND THIS INTO A PLAYABLE QUEST';
  const labels = sandbox
    ? [['Shape the world brief', 'Setting and encounter'], ['Generate pixel art', 'Tiles and sprite frames'], ['Build connected chunks', 'Godot terrain and mechanics'], ['Review the world', 'Image sheet and local vision']]
    : darkFantasy
    ? [['Design the hero', 'Class, stats, and starting area'], ['Generate the dark world', 'Random dungeons, towns, and loot'], ['Build the isometric RPG', 'Canvas combat, skills, and AI'], ['Review the loot', 'Item and monster visual feedback']]
    : [['Plan the encounter', 'Quest, cast and setting'], ['Build the playable slice', 'Offline browser RPG'], ['Shape the scene', 'Blender + FBX export'], ['Inspect the renders', 'Local visual feedback']];
  const phases = sandbox ? ['planning', 'assets', 'engine', 'review'] : darkFantasy ? ['planning', 'assets', 'engine', 'review'] : ['planning', 'browser', 'blender', 'review'];
  $$('[data-mini-phase]').forEach((node, index) => {
    node.dataset.miniPhase = phases[index];
    node.querySelector('b').textContent = labels[index][0];
    node.querySelector('small').textContent = labels[index][1];
  });
  const stepLabels = sandbox ? ['Plan', 'Pixel art', 'Godot world', 'Visual review'] : darkFantasy ? ['Plan', 'Dark world', 'Isometric RPG', 'Visual review'] : ['Plan', 'Playable game', 'Blender scene', 'Visual review'];
  $$('#job-steps [data-phase]').forEach((node, index) => {
    node.dataset.phase = phases[index];
    node.querySelector('b').textContent = stepLabels[index];
  });
  const godotNote = byId('godot-note');
  godotNote.textContent = sandbox
    ? 'Godot 4.3+ launches the game. The workbench can still review the generated world and art sheets without it.'
    : darkFantasy
    ? 'The dark fantasy RPG runs in any browser — no engine install required.'
    : 'Godot 4.3+ launches the game. The workbench can still review the generated world and art sheets without it.';
}

async function loadProjects(preferredId = '') {
  try {
    const data = await request('/api/projects');
    state.projects = data.projects || [];
    state.projectById = new Map(state.projects.map(project => [project.id, project]));
    byId('project-count').textContent = String(state.projects.length).padStart(2, '0');
    renderProjectGrid();
    const selected = state.projectById.get(preferredId) || state.selected && state.projectById.get(state.selected.id) || state.projects[0] || null;
    selectProject(selected, false);
  } catch (error) {
    toast(error.message, true);
  }
}

async function resumeActiveJob() {
  try {
    const data = await request('/api/jobs');
    const active = data.jobs?.[0];
    if (!active || state.jobId) return;
    state.jobId = active.id;
    byId('job-panel').classList.remove('hidden');
    byId('generate-button').disabled = true;
    byId('generate-button').querySelector('span:nth-child(2)').textContent = 'Generating…';
    renderJobPhase(active);
    state.pollTimer = setInterval(pollJob, 1100);
    await pollJob();
  } catch (error) { toast(error.message, true); }
}

function themeName(theme) {
  return ({'sky-dragon': 'SKY DRAGON', 'dark-fantasy': 'DARK FANTASY', adventure: 'ADVENTURE'})[theme] || String(theme || 'GAME').toUpperCase();
}

function createActionButton(text, action, projectId, className = 'card-action') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.dataset.action = action;
  button.dataset.projectId = projectId;
  button.textContent = text;
  return button;
}

function renderProjectGrid() {
  const grid = byId('project-grid');
  grid.replaceChildren();
  byId('empty-projects').classList.toggle('hidden', state.projects.length > 0);
  for (const project of state.projects) {
    const article = document.createElement('article');
    article.className = 'project-card';
    article.dataset.projectId = project.id;
    const media = document.createElement('div');
    media.className = 'project-image';
    if (project.renderUrl) {
      const image = document.createElement('img');
      image.src = project.renderUrl;
      image.alt = `${project.name} world preview`;
      image.loading = 'lazy';
      image.onerror = () => image.remove();
      media.append(image);
    }
    const tag = document.createElement('span');
    tag.className = 'theme-tag';
    tag.textContent = themeName(project.theme);
    media.append(tag);
    if (project.webReady) {
      const webTag = document.createElement('span');
      webTag.className = 'web-ready-tag';
      webTag.textContent = 'WEB READY';
      webTag.title = 'Web export available — open index.html on any device';
      media.append(webTag);
    }
    const info = document.createElement('div');
    info.className = 'project-info';
    const heading = document.createElement('h3');
    heading.textContent = project.name;
    const description = document.createElement('p');
    description.textContent = project.description || project.setting || '';
    const meta = document.createElement('div');
    meta.className = 'project-meta';
    const created = document.createElement('span');
    created.textContent = project.created || '';
    const stage = document.createElement('b');
    stage.textContent = project.review?.status === 'reviewed'
      ? (project.runtime === 'godot' ? 'ART REVIEWED' : 'REVIEWED')
      : project.runtime === 'godot' ? 'GODOT SLICE' : project.files.blend ? 'SCENE READY' : 'PLAYABLE';
    meta.append(created, stage);
    const actions = document.createElement('div');
    actions.className = 'project-card-actions';
    const openWorkspace = createActionButton('Open workspace →', 'select', project.id, 'card-select');
    let play;
    if (project.runtime === 'godot') {
      play = createActionButton('Run in Godot ↗', 'play', project.id);
    } else {
      play = document.createElement('a');
      play.className = 'card-action';
      play.href = project.url;
      play.target = '_blank';
      play.rel = 'noreferrer';
      play.textContent = 'Play ↗';
    }
    actions.append(openWorkspace, play);
    info.append(heading, description, meta, actions);
    article.append(media, info);
    grid.append(article);
  }
}

function selectProject(project, announce = true) {
  state.selected = project;
  const empty = !project;
  byId('empty-preview').classList.toggle('hidden', !empty);
  byId('output-preview').classList.toggle('hidden', empty);
  byId('preview-switch').classList.toggle('hidden', empty || project.runtime !== 'godot' || !project.artUrl);
  if (empty) {
    byId('output-title').textContent = 'Your world will appear here';
    return;
  }
  byId('output-title').textContent = project.runtime === 'godot' ? 'Your sandbox world is ready' : 'Your world, ready to explore';
  byId('preview-project-name').textContent = project.name;
  const reviewLabel = project.review?.status === 'reviewed' ? (project.runtime === 'godot' ? 'ART REVIEWED' : 'VISION REVIEWED') : project.runtime === 'godot' ? 'GODOT SLICE' : project.files.blend ? 'SCENE READY' : 'GAME READY';
  const sizeLabel = project.runtime === 'godot' ? `SEED ${project.seed} · ${project.chunks} CHUNKS` : reviewLabel;
  byId('preview-project-meta').textContent = `${project.paletteName || themeName(project.theme)} · ${sizeLabel}${project.webReady ? '  ·  WEB READY' : ''}`;
  const image = byId('output-image');
  image.src = project.renderUrl || '';
  image.alt = `${project.name} world preview`;
  image.classList.toggle('hidden', !project.renderUrl);
  image.classList.toggle('pixel-preview', project.runtime === 'godot');
  image.classList.remove('art-preview');
  $$('[data-preview-image]').forEach(button => button.classList.toggle('active', button.dataset.previewImage === 'world'));
  byId('play-game-button').textContent = project.runtime === 'godot' ? '▶ Run in Godot' : '▶ Play game';
  byId('open-blend-button').textContent = project.runtime === 'godot' ? '◈ Open Godot project' : '◈ Open in Blender';
  byId('open-blend-button').disabled = project.runtime === 'godot' ? !project.files.godot : !project.files.blend;
  const playWeb = byId('play-web-button');
  if (project.webReady) {
    playWeb.style.display = 'inline-flex';
    playWeb.onclick = (event) => {
      event.stopPropagation();
      window.open(`/project/${encodeURIComponent(project.id)}/web-export/index.html`, '_blank');
    };
  } else {
    playWeb.style.display = 'none';
  }
  byId('export-project-button').href = `/api/export/${encodeURIComponent(project.id)}.zip`;
  byId('open-project-folder').disabled = false;
  byId('open-game-tab').classList.toggle('hidden', project.runtime === 'godot');
  const links = byId('file-links');
  links.replaceChildren();
  const files = project.runtime === 'godot' ? [
    ['WORLD PREVIEW', 'world-preview.png', project.files.worldPreview],
    ['ART REVIEW SHEET', 'art-review.png', project.files.art],
    ['TILE ATLAS', 'sandbox-game/Art/tiles.png', project.files.atlas],
    ['PLAYER FRAMES', 'sandbox-game/Art/player-sheet.png', project.files.playerSheet],
    ['ENEMY FRAMES', 'sandbox-game/Art/slime-sheet.png', project.files.slimeSheet],
    ['GODOT PROJECT', 'sandbox-game/project.godot', project.files.godot],
    ['WORLD SPEC', 'world-spec.json', true],
    ['PIXEL ART REVIEW', 'pixel-art-review.json', project.files.pixelReview],
    ['GAME CONTENT', 'game-content.json', true],
    ['PROJECT MANIFEST', 'project.json', true],
  ] : project.runtime === 'browser-dark-fantasy' ? [
    ['PLAYABLE GAME', 'index.html', true],
    ['WORLD PREVIEW', 'world-preview.png', project.files.worldPreview],
    ['GAME CONTENT', 'game-content.json', true],
    ['PROJECT MANIFEST', 'project.json', true],
  ] : [
    ['FBX', 'blender-concept/concept.fbx', project.files.fbx],
    ['BLEND', 'blender-concept/concept.blend', project.files.blend],
    ['FULL RENDER', 'blender-concept/concept.png', project.files.render],
    ['FACE CLOSE-UP', 'blender-concept/character-closeup.png', project.files.closeup],
    ['VISION REVIEW', 'vision-review.json', project.files.review],
    ['GAME CONTENT', 'game-content.json', true],
    ['PROJECT MANIFEST', 'project.json', true],
  ];
  for (const [label, path, exists] of files) {
    if (!exists) continue;
    const link = document.createElement('a');
    link.href = `/project/${encodeURIComponent(project.id)}/${path}${path.endsWith('.blend') || path.endsWith('.fbx') ? '?download=1' : ''}`;
    link.textContent = label;
    if (path.endsWith('.blend') || path.endsWith('.fbx')) link.download = '';
    else { link.target = '_blank'; link.rel = 'noreferrer'; }
    links.append(link);
  }
  if (announce) toast(`${project.name} loaded into the workbench.`);
}

function renderJobPhase(job) {
  const phases = job.mode === 'sandbox'
    ? ['planning', 'assets', 'engine', 'review']
    : job.mode === 'dark-fantasy'
    ? ['planning', 'assets', 'engine', 'review']
    : ['planning', 'browser', 'blender', 'review'];
  const phaseIndex = Math.max(0, phases.indexOf(job.phase));
  const complete = ['complete', 'complete_with_warnings'].includes(job.status);
  $$('#job-steps [data-phase]').forEach((node, index) => {
    const skipped = (job.mode !== 'sandbox' && job.mode !== 'dark-fantasy' && !job.withBlender && index >= 2);
    node.classList.toggle('skipped', skipped);
    node.classList.toggle('done', !skipped && (complete ? (job.mode === 'sandbox' || job.mode === 'dark-fantasy' || job.withBlender || index < 2) : index < phaseIndex));
    node.classList.toggle('active', !skipped && !complete && index === phaseIndex);
  });
  $$('[data-mini-phase]').forEach((node, index) => {
    const skipped = (job.mode !== 'sandbox' && job.mode !== 'dark-fantasy' && !job.withBlender && index >= 2);
    node.classList.toggle('skipped', skipped);
    node.classList.toggle('done', !skipped && (complete || index < phaseIndex));
    node.classList.toggle('active', !skipped && !complete && index === phaseIndex);
  });
  const titles = {
    planning: 'Shaping the game brief…',
    assets: 'Generating the pixel-art sheets…',
    engine: job.mode === 'dark-fantasy' ? 'Building the dark world…' : 'Building the seeded Godot world…',
    browser: 'Building the playable world…',
    blender: 'Building the Blender scene…',
    review: job.mode === 'sandbox' ? 'Reviewing the pixel-art sheets locally…' : 'Reviewing the renders locally…',
    complete: 'Your game build is ready.',
    complete_with_warnings: 'The game is ready with a pipeline warning.',
    failed: 'The build stopped before completion.',
    cancelled: 'Generation was cancelled.',
  };
  byId('job-title').textContent = titles[job.status] || titles[job.phase] || 'Building your game…';
  byId('job-kicker').textContent = complete ? 'LOCAL BUILD COMPLETE' : job.status === 'failed' ? 'BUILD FAILED' : job.status === 'cancelled' ? 'BUILD CANCELLED' : 'LOCAL BUILD IN PROGRESS';
  byId('job-spinner').classList.toggle('still', job.status !== 'running');
  byId('job-spinner').textContent = job.status === 'complete' ? '✓' : job.status === 'complete_with_warnings' ? '!' : job.status === 'failed' ? '×' : job.status === 'cancelled' ? '–' : '';
  byId('cancel-button').classList.toggle('hidden', job.status !== 'running');
  byId('cancel-button').disabled = job.status !== 'running';
  byId('cancel-button').textContent = 'Cancel build';
  byId('job-log-text').textContent = job.log || 'Waiting for the local planner…';
  const details = $('.job-log');
  if (job.log) details.open = true;
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const job = await request(`/api/jobs/${encodeURIComponent(state.jobId)}`);
    renderJobPhase(job);
    if (['complete', 'complete_with_warnings', 'failed', 'cancelled'].includes(job.status)) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      if (job.status === 'complete' || job.status === 'complete_with_warnings') {
        await loadProjects(job.projectId);
        const mode = job.mode === 'sandbox' ? 'Godot sandbox and pixel art' : 'Game and local artifacts';
        toast(job.status === 'complete' ? `${mode} are ready.` : `The ${mode.toLowerCase()} are ready; inspect the pipeline log for a warning.`, job.status !== 'complete');
      } else {
        toast(job.status === 'cancelled' ? 'Build cancelled.' : 'The build failed. Open the local log below for details.', true);
      }
      byId('generate-button').disabled = false;
      byId('generate-button').querySelector('span:nth-child(2)').textContent = 'Generate game';
      state.jobId = null;
      return;
    }
  } catch (error) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
    byId('generate-button').disabled = false;
    toast(error.message, true);
  }
}

async function startGeneration() {
  const idea = byId('idea-input').value.trim();
  const errorNode = byId('form-error');
  errorNode.textContent = '';
  if (!idea) {
    errorNode.textContent = 'Add a game idea to begin.';
    byId('idea-input').focus();
    return;
  }
  const mode = byId('game-mode').value;
  if (mode === 'quest' && byId('with-blender').checked && !byId('blender-dot').classList.contains('online')) {
    errorNode.textContent = 'Blender is unavailable. Turn off the Blender scene option to build the game slice only.';
    return;
  }
  const seed = Number(byId('world-seed').value);
  if (mode === 'sandbox' && (!Number.isInteger(seed) || seed < 0 || seed > 2147483647)) {
    errorNode.textContent = 'Enter a whole-number world seed between 0 and 2147483647.';
    byId('world-seed').focus();
    return;
  }
  byId('generate-button').disabled = true;
  byId('generate-button').querySelector('span:nth-child(2)').textContent = 'Starting local build…';
  try {
    const response = await post('/api/generate', {
      idea,
      title: byId('title-input').value.trim(),
      mode,
      seed: mode === 'sandbox' ? seed : 4172026,
      chunks: Number(byId('world-chunks').value),
      palette: byId('world-palette').value,
      difficulty: byId('difficulty').value,
      biome: byId('world-biome').value,
      enemyCount: Number(byId('enemy-count').value),
      enemyBehavior: byId('enemy-behavior').value,
      startingWood: Number(byId('starting-wood').value),
      startingDirt: Number(byId('starting-dirt').value),
      gravity: Number(byId('gravity').value),
      jumpHeight: Number(byId('jump-height').value),
      moveSpeed: Number(byId('move-speed').value),
      cameraZoom: Number(byId('camera-zoom').value),
      saveInterval: Number(byId('save-interval').value),
      chaos: Number(byId('chaos').value),
      reviewStrictness: byId('review-strictness').value,
      plannerModel: byId('planner-model').value,
      visionModel: byId('vision-model').value,
      withBlender: byId('with-blender').checked,
      withReview: byId('with-review').checked,
      targetProject: byId('target-project').value.trim(),
    });
    state.jobId = response.id;
    byId('job-panel').classList.remove('hidden');
    renderJobPhase(response);
    byId('generate-button').querySelector('span:nth-child(2)').textContent = 'Generating…';
    setView('create');
    state.pollTimer = setInterval(pollJob, 1100);
    await pollJob();
  } catch (error) {
    byId('generate-button').disabled = false;
    byId('generate-button').querySelector('span:nth-child(2)').textContent = 'Generate game';
    errorNode.textContent = error.message;
  }
}

async function openLocal(action, projectId = state.selected?.id) {
  if (!projectId) return toast('Choose a project first.', true);
  try {
    await post('/api/open', {action, projectId});
    const message = action === 'blender' ? 'Opening the scene in Blender…'
      : action === 'game' ? 'Launching the game in Godot…'
      : action === 'godot-editor' ? 'Opening the Godot project…'
      : 'Opening the project folder…';
    toast(message);
  } catch (error) { toast(error.message, true); }
}

async function exportWeb(projectId = state.selected?.id) {
  if (!projectId) return toast('Choose a project first.', true);
  byId('export-web-button').disabled = true;
  const original = byId('export-web-button').textContent;
  byId('export-web-button').textContent = 'Building web export…';
  try {
    const response = await fetch(`/api/export-web/${encodeURIComponent(projectId)}.zip`);
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json()).error || ''; } catch (_) {}
      throw new Error(detail || `Web export failed (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectId}-web.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('Web export ready — unzip and open index.html on any device.', false);
    // Auto-open the exported package so it's playable immediately.
    try {
      window.open(`/project/${encodeURIComponent(projectId)}/web-export/index.html`, '_blank');
    } catch (_) { /* popup blocked; the zip download still succeeded */ }
  } catch (error) {
    toast(error.message, true);
  } finally {
    byId('export-web-button').disabled = false;
    byId('export-web-button').textContent = original;
  }
}

function openGame(project = state.selected) {
  if (!project) return toast('Generate or select a game first.', true);
  if (project.runtime === 'godot') return openLocal('game', project.id);
  byId('modal-title').textContent = project.name;
  byId('game-frame').src = project.url;
  byId('open-game-tab').href = project.url;
  byId('game-modal').classList.remove('hidden');
  document.body.classList.add('modal-open');
}

function closeGame() {
  byId('game-modal').classList.add('hidden');
  byId('game-frame').src = 'about:blank';
  document.body.classList.remove('modal-open');
}

function updateIdeaCount() {
  byId('idea-count').textContent = `${byId('idea-input').value.length} / 4000`;
}

function syncReviewOption() {
  const enabled = byId('with-blender').checked && !byId('with-blender').disabled;
  byId('with-review').disabled = !enabled;
  byId('with-review').closest('.check-row').classList.toggle('disabled', !enabled);
}

document.addEventListener('click', event => {
  const preview = event.target.closest('[data-preview-image]');
  if (preview && state.selected) {
    const artSelected = preview.dataset.previewImage === 'art' && state.selected.artUrl;
    byId('output-image').src = artSelected || state.selected.renderUrl || '';
    byId('output-image').alt = artSelected ? `${state.selected.name} pixel-art sheet` : `${state.selected.name} world preview`;
    byId('output-image').classList.toggle('art-preview', Boolean(artSelected));
    $$('[data-preview-image]').forEach(button => button.classList.toggle('active', button === preview));
  }
  const nav = event.target.closest('[data-view]');
  if (nav) setView(nav.dataset.view);
  const go = event.target.closest('[data-go]');
  if (go) setView(go.dataset.go);
  const chip = event.target.closest('[data-prompt]');
  if (chip) {
    byId('idea-input').value = chip.dataset.prompt;
    updateIdeaCount();
    byId('idea-input').focus();
  }
  const action = event.target.closest('[data-action]');
  if (action) {
    const project = state.projectById.get(action.dataset.projectId);
    if (action.dataset.action === 'select') {
      selectProject(project);
      setView('create');
    } else if (action.dataset.action === 'play') {
      openLocal('game', project.id);
    }
  }
});

byId('idea-input').addEventListener('input', updateIdeaCount);
byId('generate-button').addEventListener('click', startGeneration);
byId('game-mode').addEventListener('change', syncGenerationMode);
byId('refresh-button').addEventListener('click', () => { loadStatus(); loadProjects(); toast('Workspace refreshed.'); });
byId('stop-server').addEventListener('click', async () => {
  try {
    await post('/api/shutdown', {});
    toast('Workbench stopped. Reopen Vibe Create from the Desktop to start it again.');
    byId('stop-server').disabled = true;
  } catch (error) { toast(error.message, true); }
});
byId('with-blender').addEventListener('change', syncGenerationMode);
byId('play-game-button').addEventListener('click', () => openGame());
byId('export-web-button').addEventListener('click', exportWeb);
byId('open-blend-button').addEventListener('click', () => openLocal(state.selected?.runtime === 'godot' ? 'godot-editor' : 'blender'));
byId('open-project-folder').addEventListener('click', () => openLocal('folder'));
byId('pick-target').addEventListener('click', async () => {
  try {
    const result = await post('/api/pick-target', {});
    if (result.path) {
      byId('target-project').value = result.path;
      toast('Unreal project selected.');
    }
  } catch (error) { toast(error.message, true); }
});
byId('cancel-button').addEventListener('click', async () => {
  if (!state.jobId) return;
  byId('cancel-button').textContent = 'Cancelling…';
  byId('cancel-button').disabled = true;
  try { await post('/api/cancel', {jobId: state.jobId}); }
  catch (error) { toast(error.message, true); }
});
byId('close-game').addEventListener('click', closeGame);
byId('game-modal').addEventListener('click', event => { if (event.target.id === 'game-modal') closeGame(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !byId('game-modal').classList.contains('hidden')) closeGame(); });
byId('open-game-tab').addEventListener('click', event => { if (!state.selected) event.preventDefault(); });

syncGenerationMode();
updateIdeaCount();
loadStatus();
loadProjects();
resumeActiveJob();
