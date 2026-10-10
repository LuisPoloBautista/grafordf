const search = document.querySelector('#search');
const results = document.querySelector('#results');
const detail = document.querySelector('#detail');
const stats = document.querySelector('#stats');
const more = document.querySelector('#more');
const typeFilter = document.querySelector('#type-filter');
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
Object.assign(labels, {title: 'Título', mainTitle: 'Título principal', contribution: 'Autoría', agent: 'Autor', provisionActivity: 'Publicación', date: 'Fecha', language: 'Idioma', genreForm: 'Tipo de documento', subject: 'Área temática', extent: 'Extensión', note: 'Notas', editionStatement: 'Edición', identifiedBy: 'Identificador', electronicLocator: 'Acceso al documento', instanceOf: 'Obra', sourceFile: 'Archivo fuente', sourceRow: 'Fila del CSV', matchMethod: 'Criterio de vinculación', value: 'Valor', 'bibliografia-volumen': 'Volumen', 'bibliografia-pagina-inicio': 'Página inicial', 'bibliografia-pagina-fin': 'Página final', 'bibliografia-no-referencias': 'Número de referencias', 'bibliografia-referentes': 'Referentes', 'bibliografia-pdf': 'PDF disponible', 'bibliografia-tomo': 'Tomo', 'bibliografia-numero': 'Número'});
const escapeHtml = value => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const formatKey = key => escapeHtml(labels[key] || key.replace(/([A-Z])/g, ' $1'));

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Error ${response.status}`);
  return response.json();
}

function linkText(text) {
  return String(text).split(/(https?:\/\/[^\s<>"']+)/g).map(part => /^https?:\/\//.test(part)
    ? `<a href="${escapeHtml(part)}" target="_blank" rel="noopener noreferrer">${escapeHtml(part)}</a>` : escapeHtml(part)).join('');
}
function renderValue(item) {
  if (!item || typeof item !== 'object') return linkText(item);
  if (item.facet_id) {
    const external = item.external ? ` <a href="${escapeHtml(item.external)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir fuente externa">↗</a>` : '';
    return `<a href="#metadato=${encodeURIComponent(item.facet_id)}">${escapeHtml(item.label)}</a>${external}`;
  }
  if (item.id.startsWith('http://ahcm/persona/') && item.id.split('/').length === 5) {
    return `<a href="#persona=${encodeURIComponent(item.id.split('/').pop())}">${escapeHtml(item.label)}</a>`;
  }
  if (item.id.startsWith('http://ahcm/')) {
    return `<a href="#recurso=${encodeURIComponent(item.id)}">${escapeHtml(item.label)}</a>`;
  }
  if (/^https?:\/\//i.test(item.id)) return `<a href="${escapeHtml(item.id)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.label)}</a>`;
  return linkText(item.label);
}
function propertyTable(properties) {
  return `<table class="metadata"><tbody>${Object.entries(properties)
    .filter(([key]) => !['type', 'identifier', 'label', 'hasInstance'].includes(key))
    .map(([key, items]) => `<tr><th scope="row">${formatKey(key)}</th><td>${items.map(renderValue).join('<br>')}</td></tr>`).join('')}</tbody></table>`;
}

async function searchPeople(append = false) {
  const version = ++searchVersion;
  if (!append) { offset = 0; results.innerHTML = '<p class="muted">Consultando…</p>'; }
  more.hidden = true;
  try {
    // Ask for one extra item to determine whether another page exists.
    const data = await getJSON(`/api/buscar?q=${encodeURIComponent(search.value.trim())}&kind=${typeFilter.value}&limit=${pageSize + 1}&offset=${offset}`);
    if (version !== searchVersion) return;
    if (!append) results.innerHTML = '';
    const page = data.slice(0, pageSize);
    results.insertAdjacentHTML('beforeend', page.map(item => `<button class="result" data-kind="${escapeHtml(item.kind)}" data-id="${escapeHtml(item.id)}"><strong>${escapeHtml(item.label)}</strong><small>${item.kind === 'actor' ? 'Actor' : 'Publicación'}</small></button>`).join(''));
    if (!page.length && !append) results.innerHTML = '<p class="muted">No se encontraron registros.</p>';
    offset += page.length;
    more.hidden = data.length <= pageSize;
  } catch (_) {
    if (version !== searchVersion) return;
    if (!append) results.innerHTML = '';
    results.insertAdjacentHTML('beforeend', '<p class="muted">No se pudo cargar la búsqueda. <button id="retry-search">Reintentar</button></p>');
    document.querySelector('#retry-search').onclick = () => searchPeople();
  }
}

async function loadPerson(id) {
  const version = ++detailVersion;
  detail.className = 'detail';
  detail.innerHTML = '<p class="muted">Cargando ficha…</p>';
  try {
    const person = await getJSON(`/api/personas/${encodeURIComponent(id)}`);
    if (version !== detailVersion) return;
    detail.innerHTML = `<p class="eyebrow">Ficha de autoridad</p><h2>${escapeHtml(person.label)}</h2>
      ${propertyTable(person.properties)}
      <section class="publications"><h3>Publicaciones vinculadas (${person.publications.length})</h3>
      ${person.publications.length ? `<ul>${person.publications.map(item => `<li>${renderValue(item)}</li>`).join('')}</ul>` : '<p class="muted">No hay publicaciones vinculadas.</p>'}</section>
      <section class="publications"><h3>Subgrafo del actor</h3><p class="hint">Actores, metadatos y publicaciones. Arrastra los nodos o acerca la vista.</p>
      <iframe title="Subgrafo del actor" src="/api/personas/${encodeURIComponent(id)}/grafo" loading="lazy"></iframe></section>`;
  } catch (_) {
    if (version === detailVersion) detail.innerHTML = '<p>No se pudo cargar la ficha. Selecciona la persona para reintentar.</p>';
  }
}
async function loadResource(uri) {
  const version = ++detailVersion;
  detail.className = 'detail';
  detail.innerHTML = '<p>Cargando metadatos…</p>';
  try {
    const resource = await getJSON(`/api/recursos?uri=${encodeURIComponent(uri)}`);
    if (version !== detailVersion) return;
    detail.innerHTML = `<p class="eyebrow">${uri.startsWith('http://ahcm/publicacion/') ? 'Ficha bibliográfica · BIBFRAME' : 'Ficha de recurso'}</p>
      <h2>${escapeHtml(resource.label)}</h2>${propertyTable(resource.properties)}
      ${resource.actors.length ? `<p>Actores vinculados: ${resource.actors.map(renderValue).join('; ')}</p>` : ''}
      ${resource.instances.map(instance => `<section class="publications"><h3>Edición · ${escapeHtml(instance.label)}</h3>${propertyTable(instance.properties)}</section>`).join('')}
      ${uri.startsWith('http://ahcm/publicacion/') && !resource.instances.length ? '<p class="hint">Título registrado por el actor, sin coincidencia bibliográfica única en el CSV.</p>' : ''}`;
  } catch (_) {
    if (version === detailVersion) detail.innerHTML = '<p>No se pudo cargar el recurso.</p>';
  }
}
async function loadMetadata(id, append = false) {
  const version = append ? detailVersion : ++detailVersion;
  const current = append ? Number(detail.dataset.offset || 0) : 0;
  detail.className = 'detail';
  if (!append) detail.innerHTML = '<p>Cargando registros relacionados…</p>';
  try {
    const data = await getJSON(`/api/metadatos?id=${encodeURIComponent(id)}&offset=${current}&limit=30`);
    if (version !== detailVersion) return;
    if (!append) detail.innerHTML = `<p class="eyebrow">Metadato compartido</p><h2>${escapeHtml(data.label)}</h2>
      <p>${data.total} registros relacionados</p><ul id="related-records"></ul><button id="more-related" hidden>Mostrar más registros</button>`;
    detail.querySelector('#related-records').insertAdjacentHTML('beforeend', data.records.map(item => `<li>${renderValue(item)} <span class="muted">${item.kind === 'actor' ? 'Actor' : 'Publicación'}</span></li>`).join(''));
    detail.dataset.offset = current + data.records.length;
    const button = detail.querySelector('#more-related');
    button.hidden = current + data.records.length >= data.total;
    button.onclick = () => { button.disabled = true; loadMetadata(id, true).finally(() => { button.disabled = false; }); };
  } catch (_) {
    if (version === detailVersion) detail.innerHTML = '<p>No se pudieron cargar los registros relacionados.</p>';
  }
}
function route() {
  const fragment = new URLSearchParams(location.hash.slice(1));
  if (fragment.has('persona')) loadPerson(fragment.get('persona'));
  else if (fragment.has('recurso')) loadResource(fragment.get('recurso'));
  else if (fragment.has('metadato')) loadMetadata(fragment.get('metadato'));
  else { ++detailVersion; detail.className = 'detail empty-state'; detail.innerHTML = '<h2>Selecciona un registro</h2>'; }
}
window.addEventListener('hashchange', route);

results.addEventListener('click', event => {
  const button = event.target.closest('[data-id]');
  if (button) { const hash = button.dataset.kind === 'actor' ? '#persona=' + encodeURIComponent(button.dataset.id.split('/').pop()) : '#recurso=' + encodeURIComponent(button.dataset.id); if (location.hash === hash) route(); else location.hash = hash; }
});
search.addEventListener('input', () => {
  ++searchVersion;
  more.hidden = true;
  clearTimeout(timer);
  timer = setTimeout(() => searchPeople(), 250);
});
more.addEventListener('click', () => searchPeople(true));
typeFilter.addEventListener('change', () => { clearTimeout(timer); searchPeople(); });
document.querySelector('#clear').addEventListener('click', () => {
  clearTimeout(timer);
  ++detailVersion;
  history.replaceState(null, '', location.pathname);
  search.value = '';
  typeFilter.value = 'todos';
  detail.className = 'detail empty-state';
  detail.innerHTML = '<h2>Selecciona una persona</h2><p>Consulta su información, publicaciones y relaciones.</p>';
  search.focus();
  searchPeople();
});
getJSON('/api/stats').then(data => {
  stats.innerHTML = `<span>${data.personas} personas</span><span>${data.publicaciones} publicaciones</span><span>${data.triples} relaciones RDF</span>`;
}).catch(() => { stats.textContent = 'Estadísticas no disponibles'; });
getJSON('/api/vocabulario').then(data => Object.assign(labels, data.labels)).catch(() => {}).finally(() => { searchPeople(); route(); });
