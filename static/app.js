const search = document.querySelector('#search');
const results = document.querySelector('#results');
const detail = document.querySelector('#detail');
const stats = document.querySelector('#stats');
const more = document.querySelector('#more');
let timer, searchVersion = 0, detailVersion = 0, offset = 0;
const pageSize = 20;
const labels = {
  NameChange: 'Firma', alternateName: 'Abreviatura', gender: 'Género',
  primaryRole: 'Rol principal', acquiredRole: 'Rol adquirido', community: 'Comunidad',
  subcommunity: 'Subcomunidad', birthPlace: 'Lugar de nacimiento', deathPlace: 'Lugar de muerte',
  birth: 'Año de nacimiento', death: 'Año de muerte', educationalTraining: 'Formación',
  hasOccupation: 'Profesión', degree: 'Grado', memberOf: 'Adscripción', jobTitle: 'Cargo',
  affiliation: 'Afiliación', awardOrHonor: 'Reconocimientos', geographicFocus: 'Movilidad',
  advisorIn: 'Linaje científico', adviseeIn: 'Linaje descendiente', altLabel: 'Epónimo recibido',
  wasAttributedTo: 'Otorgado por', assignedEponym: 'Epónimo asignado', awardedTo: 'Otorgado a',
  comment: 'Notas', made: 'Publicación o aportación', externalLink: 'Identificador externo'
};
const escapeHtml = value => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const formatKey = key => escapeHtml(labels[key] || key.replace(/([A-Z])/g, ' $1'));

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Error ${response.status}`);
  return response.json();
}

function renderValue(item) {
  if (!item || typeof item !== 'object') return escapeHtml(item);
  // RDF identifiers are not necessarily navigable web pages.
  if (/^https?:\/\//i.test(item.id) && !item.id.startsWith('http://ahcm/')) {
    return `<a href="${escapeHtml(item.id)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.label)}</a>`;
  }
  return escapeHtml(item.label);
}

async function searchPeople(append = false) {
  const version = ++searchVersion;
  if (!append) { offset = 0; results.innerHTML = '<p class="muted">Consultando…</p>'; }
  more.hidden = true;
  try {
    // Ask for one extra item to determine whether another page exists.
    const data = await getJSON(`/api/personas?q=${encodeURIComponent(search.value.trim())}&limit=${pageSize + 1}&offset=${offset}`);
    if (version !== searchVersion) return;
    if (!append) results.innerHTML = '';
    const page = data.slice(0, pageSize);
    results.insertAdjacentHTML('beforeend', page.map(person => `<button class="result" data-id="${escapeHtml(person.slug)}"><strong>${escapeHtml(person.label)}</strong><small>Ver ficha</small></button>`).join(''));
    if (!page.length && !append) results.innerHTML = '<p class="muted">No se encontraron personas.</p>';
    offset += page.length;
    more.hidden = data.length <= pageSize;
  } catch (_) {
    if (version !== searchVersion) return;
    if (!append) results.innerHTML = '';
    results.insertAdjacentHTML('beforeend', '<p class="muted">No se pudo cargar la búsqueda. <button id="retry-search">Reintentar</button></p>');
    document.querySelector('#retry-search').onclick = () => searchPeople();
  }
}

function drawGraph(person, relations) {
  const container = document.querySelector('#graph');
  const items = relations.slice(0, 16);
  if (!items.length) { container.textContent = 'No hay relaciones enlazadas.'; return; }
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 760 560');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Relaciones de ${person.label}. Lista completa debajo.`);
  const add = (name, attrs, text) => {
    const node = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v));
    if (text) node.textContent = text;
    svg.appendChild(node);
    return node;
  };
  const positions = items.map((item, i) => {
    const angle = 2 * Math.PI * i / items.length;
    return {item, x: 380 + 255 * Math.cos(angle), y: 275 + 210 * Math.sin(angle)};
  });
  positions.forEach(({x,y}) => add('line', {x1:380,y1:275,x2:x,y2:y,stroke:'#a9c7c0','stroke-width':2}));
  positions.forEach(({item,x,y}) => {
    const node = add('circle', {cx:x,cy:y,r:10,fill:'#c65d3a'});
    const title = document.createElementNS(ns,'title');
    title.textContent = `${labels[item.predicate] || item.predicate}: ${item.target.label}`;
    node.appendChild(title);
    add('text',{x,y:y+26,'text-anchor':'middle','font-size':12,fill:'#17252d'},
        item.target.label.length > 26 ? item.target.label.slice(0,23) + '…' : item.target.label);
  });
  add('circle',{cx:380,cy:275,r:24,fill:'#246b68'});
  add('text',{x:380,y:319,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#17252d'},person.label);
  container.appendChild(svg);
}

async function loadPerson(id) {
  const version = ++detailVersion;
  detail.className = 'detail';
  detail.innerHTML = '<p class="muted">Cargando ficha…</p>';
  try {
    const [person, relations] = await Promise.all([
      getJSON(`/api/personas/${encodeURIComponent(id)}`),
      getJSON(`/api/personas/${encodeURIComponent(id)}/relaciones`)
    ]);
    if (version !== detailVersion) return;
    const properties = Object.entries(person.properties).filter(([key]) => !['type','name','identifier','made'].includes(key));
    const contributions = (person.properties.made || []).filter(item => !person.publications.some(work => work.id === item.id));
    if (contributions.length) properties.push(['made', contributions]);
    detail.innerHTML = `<p class="eyebrow">Ficha de entidad</p><h2>${escapeHtml(person.label)}</h2>
      <div class="property-grid">${properties.map(([key,items]) => `<article class="property"><h3>${formatKey(key)}</h3><p>${items.map(renderValue).join('; ')}</p></article>`).join('')}</div>
      <section class="publications"><h3>Publicaciones vinculadas (${person.publications.length})</h3>${person.publications.length ? `<ul>${person.publications.map(item => `<li>${escapeHtml(item.label)}</li>`).join('')}</ul>` : '<p class="muted">No hay publicaciones vinculadas.</p>'}</section>
      <section class="publications"><h3>Relaciones del grafo (${relations.length})</h3><div id="graph"></div>
      <p class="hint">La vista muestra hasta 16 relaciones. La lista contiene todas las relaciones registradas.</p>
      ${relations.length ? `<ul>${relations.map(item => `<li><strong>${formatKey(item.predicate)}:</strong> ${renderValue(item.target)}</li>`).join('')}</ul>` : ''}</section>`;
    drawGraph(person, relations);
  } catch (_) {
    if (version === detailVersion) detail.innerHTML = '<p>No se pudo cargar la ficha. Selecciona la persona para reintentar.</p>';
  }
}

results.addEventListener('click', event => {
  const button = event.target.closest('[data-id]');
  if (button) loadPerson(button.dataset.id);
});
search.addEventListener('input', () => {
  ++searchVersion;
  more.hidden = true;
  clearTimeout(timer);
  timer = setTimeout(() => searchPeople(), 250);
});
more.addEventListener('click', () => searchPeople(true));
document.querySelector('#clear').addEventListener('click', () => {
  clearTimeout(timer);
  ++detailVersion;
  search.value = '';
  detail.className = 'detail empty-state';
  detail.innerHTML = '<h2>Selecciona una persona</h2><p>Consulta su información, publicaciones y relaciones.</p>';
  search.focus();
  searchPeople();
});
getJSON('/api/stats').then(data => {
  stats.innerHTML = `<span>${data.personas} personas</span><span>${data.publicaciones} publicaciones</span><span>${data.triples} relaciones RDF</span>`;
}).catch(() => { stats.textContent = 'Estadísticas no disponibles'; });
searchPeople();
