// SmartLight · Painel das casas
// 1. Vai buscar o país e o fuso de cada casa (nos.php) e o estado atual (ultimas.php).
// 2. Desenha a planta de cada casa; cada divisão acende com a intensidade do LED.
// 3. Ao clicar numa divisão, mostra o detalhe, o histórico de 24 h e o consumo de hoje.
'use strict';

const INTERVALO_MS = 15000;      // o estado atualiza ao mesmo ritmo a que os nós enviam
const ESCONDER_S = 86400;        // divisões sem leituras há mais de 24 h não aparecem
const P_100_MW = 17.9;           // potência de um LED a 100 %, em mW
const PAISES = { PT: 'Portugal', CH: 'Suíça' };

// Lugar de cada divisão na planta: [coluna, andar, largura, altura] numa grelha de 6 colunas e 2 andares.
// As divisões que não estão aqui são arrumadas automaticamente.
const PLANTAS = {
  no2: { corredor: [1, 1, 2, 2], quarto: [3, 1, 4, 2] },
};

let casas = {};         // no_id -> { pais, fuso }
let pacote = null;      // última resposta do estado
let escolhida = null;   // { no, div }
let grafico = null;

const $ = (id) => document.getElementById(id);

// ---------- pequenas ajudas ----------
function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

function haQuanto(seg) {
  if (seg < 60) return `${Math.round(seg)} s`;
  if (seg < 3600) return `${Math.round(seg / 60)} min`;
  if (seg < 86400) return `${Math.round(seg / 3600)} h`;
  return `${Math.round(seg / 86400)} dias`;
}

function nomeCasa(no) {
  const m = /^no(\d+)$/.exec(no);
  return m ? `Casa ${m[1]}` : no;
}

function nomeDiv(d) {
  return d.charAt(0).toUpperCase() + d.slice(1);
}

// Hora local de uma casa, a partir do fuso guardado no servidor
function horaLocal(fuso, ts) {
  const data = ts ? new Date(ts * 1000) : new Date();
  return data.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', timeZone: fuso || 'Europe/Lisbon' });
}

// Luz ambiente com a unidade certa para cada tipo de sensor
function textoLuz(l) {
  if (l.luz_raw === null || l.luz_raw === undefined) return 'sem leitura';
  const raw = Number(l.luz_raw);
  if (l.sensor_luz === 'lux') return `${Math.round(raw)} lx`;
  if (l.sensor_luz === 'digital') return raw === 1 ? 'escuro' : 'claro';
  return `${Math.round(raw / 4095 * 100)} %`;            // analógico: 0 a 4095, alto = claro
}

// ---------- pedidos ao dados.php ----------
async function pedir(params) {
  const r = await fetch('dados.php?' + new URLSearchParams(params), { cache: 'no-store' });
  const corpo = await r.json();
  if (!r.ok) throw new Error(corpo.erro || `erro ${r.status}`);
  return corpo;
}

// ---------- agrupar as leituras: casa -> divisão -> última leitura ----------
function agrupar(leituras, agora) {
  const porCasa = {};
  for (const l of leituras) {
    porCasa[l.no_id] = porCasa[l.no_id] || {};
    porCasa[l.no_id][l.divisao] = l;
  }
  // Esconde divisões paradas há mais de 24 h, se a casa tiver outras com leituras recentes
  for (const divs of Object.values(porCasa)) {
    const recente = Math.max(...Object.values(divs).map((l) => l.ts));
    if (agora - recente > ESCONDER_S) continue;
    for (const [d, l] of Object.entries(divs)) if (agora - l.ts > ESCONDER_S) delete divs[d];
  }
  return porCasa;
}

// Lugar da divisão na planta: o definido em PLANTAS ou um lugar automático
function lugar(no, div, i, total) {
  const fixo = PLANTAS[no] && PLANTAS[no][div];
  if (fixo) return fixo;
  if (total === 1) return [1, 1, 6, 2];                       // uma divisão ocupa a casa toda
  if (total === 2) return [1 + i * 3, 1, 3, 2];               // duas lado a lado
  return [1 + (i % 2) * 3, 1 + Math.floor(i / 2), 3, 1];      // três ou quatro: duas por andar
}

// ---------- desenhar as casas ----------
// Cada casa é um desenho SVG: um triângulo (telhado), um retângulo (paredes)
// e um retângulo por divisão. A divisão fica mais amarela quanto mais forte o LED.
const CORES = ['#2563A8', '#0F7C8C', '#5048A8', '#2F5D86'];   // uma cor por casa
const LUZ = '#FFC94A';                                          // cor da luz acesa
const COLUNA = 340 / 6;                                         // largura de uma coluna (as paredes têm 340)
const ANDAR = 85;                                               // altura de um andar

// Bandeiras simplificadas, desenhadas com retângulos
const BANDEIRAS = {
  CH: '<svg viewBox="0 0 32 32" class="bandeira" aria-hidden="true"><rect width="32" height="32" fill="#D52B1E"/><rect x="13" y="6" width="6" height="20" fill="#fff"/><rect x="6" y="13" width="20" height="6" fill="#fff"/></svg>',
  PT: '<svg viewBox="0 0 30 20" class="bandeira" aria-hidden="true"><rect width="12" height="20" fill="#046A38"/><rect x="12" width="18" height="20" fill="#DA291C"/><circle cx="12" cy="10" r="4" fill="#FFE900"/></svg>',
};

// Cria um elemento SVG com os atributos indicados
function svg(tag, attrs) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
}

function desenharCasa(no, divs, cor) {
  const ultima = Math.max(...Object.values(divs).map((l) => l.ts));
  const atraso = pacote.agora - ultima;
  const comunica = atraso <= pacote.offline_s;

  const casa = el('article', 'casa' + (comunica ? '' : ' sem-comunicacao'));
  casa.style.setProperty('--cor-casa', cor);
  const cab = el('div', 'casa-cab');
  cab.append(el('h3', '', nomeCasa(no)));
  cab.append(el('span', 'comunica ' + (comunica ? 'ok' : 'sem'),
    comunica ? 'A comunicar' : `Sem comunicação há ${haQuanto(atraso)}`));
  casa.append(cab);

  // Desenho: telhado, chaminé e paredes
  const d = svg('svg', { viewBox: '0 0 400 300', class: 'desenho', role: 'group', 'aria-label': nomeCasa(no) });
  const traco = comunica ? '' : '10 7';                 // contorno tracejado quando não comunica
  d.append(svg('rect', { x: 285, y: 35, width: 30, height: 60, fill: cor }));
  d.append(svg('polygon', { points: '10,112 200,20 390,112', fill: cor }));
  d.append(svg('rect', { x: 30, y: 110, width: 340, height: 170, fill: '#fff', stroke: cor, 'stroke-width': 6, 'stroke-dasharray': traco }));

  // Divisões dentro das paredes
  const nomes = Object.keys(divs);
  nomes.forEach((div, i) => {
    const l = divs[div];
    const [col, lin, larg, alt] = lugar(no, div, i, nomes.length);
    const x = 30 + (col - 1) * COLUNA, y = 110 + (lin - 1) * ANDAR;
    const w = larg * COLUNA, h = alt * ANDAR;
    const parada = pacote.agora - l.ts > pacote.offline_s;
    const led = Number(l.led_pct) || 0;
    const pres = !parada && Number(l.presenca) === 1;
    const escolha = escolhida && escolhida.no === no && escolhida.div === div;

    const g = svg('g', { class: 'sala' + (escolha ? ' escolhida' : ''), tabindex: 0, role: 'button',
      'aria-label': `${nomeDiv(div)}: ${parada ? 'sem leituras' : `LED ${led} %, ${pres ? 'com presença' : 'vazia'}`}` });
    g.append(svg('rect', { x, y, width: w, height: h, fill: parada ? '#E3E9F0' : LUZ,
      'fill-opacity': parada ? 1 : led / 100, stroke: cor, 'stroke-width': escolha ? 7 : 3 }));

    const nome = svg('text', { x: x + 10, y: y + 26, class: 'sala-nome' });
    nome.textContent = nomeDiv(div);
    g.append(nome);
    if (pres) g.append(svg('circle', { cx: x + w - 16, cy: y + 20, r: 7, class: 'pessoa' }));   // ponto = alguém na divisão

    const info = svg('text', { x: x + 10, y: y + h - 12, class: 'sala-info' });
    info.textContent = parada ? `sem leituras há ${haQuanto(pacote.agora - l.ts)}` : `LED ${led} %`;
    g.append(info);

    g.addEventListener('click', () => escolher(no, div));
    g.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); escolher(no, div); } });
    d.append(g);
  });
  casa.append(d);
  return casa;
}

// Agrupa as casas por país; cada país tem o seu cabeçalho com a hora local
function desenharCasas() {
  const caixa = $('casas');
  caixa.replaceChildren();
  const porCasa = agrupar(pacote.leituras, pacote.agora);
  const ids = Object.keys(porCasa).sort((a, b) => a.localeCompare(b, 'pt', { numeric: true }));

  const porPais = {};
  ids.forEach((no, i) => {
    const pais = (casas[no] || {}).pais || '?';
    (porPais[pais] = porPais[pais] || []).push({ no, cor: CORES[i % CORES.length] });
  });

  for (const [pais, lista] of Object.entries(porPais)) {
    const grupo = el('section', 'pais');
    const cab = el('div', 'pais-cab');
    const titulo = el('h2');
    titulo.innerHTML = BANDEIRAS[pais] || '';
    titulo.append(PAISES[pais] || pais);
    cab.append(titulo);
    cab.append(el('span', 'pais-hora', 'hora local ' + horaLocal((casas[lista[0].no] || {}).fuso)));
    grupo.append(cab);

    const fila = el('div', 'fila-casas');
    for (const { no, cor } of lista) fila.append(desenharCasa(no, porCasa[no], cor));
    grupo.append(fila);
    caixa.append(grupo);
  }
}

// ---------- detalhe da divisão escolhida ----------
function desenharValores() {
  if (!escolhida) return;
  const l = pacote.leituras.find((x) => x.no_id === escolhida.no && x.divisao === escolhida.div);
  if (!l) return;
  const info = casas[escolhida.no] || {};
  $('det-casa').textContent = `${nomeCasa(escolhida.no)} · ${PAISES[info.pais] || info.pais || ''}`;
  $('det-titulo').textContent = nomeDiv(escolhida.div);

  const linhas = [
    ['Presença', Number(l.presenca) === 1 ? 'sim' : 'não'],
    ['LED', `${Number(l.led_pct) || 0} %`],
    ['Modo', l.modo === 'auto' ? 'automático' : (l.modo || '')],
    ['Luz ambiente', textoLuz(l)],
    ['Última leitura', `${horaLocal(info.fuso, l.ts)} (há ${haQuanto(pacote.agora - l.ts)})`],
  ];
  if (l.corrente_ma !== null && l.corrente_ma !== undefined) linhas.splice(2, 0, ['Corrente', `${l.corrente_ma} mA`]);

  const dl = $('det-valores');
  dl.replaceChildren();
  for (const [t, v] of linhas) { dl.append(el('dt', '', t)); dl.append(el('dd', '', v)); }
}

// Consumo de hoje (desde a meia-noite na hora local da casa), em mWh.
// A poupança compara com a luz a 100 % apenas durante o tempo em que esteve acesa (RF26).
// Cada leitura conta durante o tempo até à leitura seguinte, no máximo 60 s,
// para uma falha de comunicação não contar como luz acesa.
function consumoHoje(leituras, no, fuso) {
  const agora = Math.floor(Date.now() / 1000);
  const p = new Intl.DateTimeFormat('en-GB', { timeZone: fuso || 'Europe/Lisbon', hour: 'numeric', minute: 'numeric', second: 'numeric', hourCycle: 'h23' })
    .formatToParts(new Date()).reduce((o, x) => ({ ...o, [x.type]: Number(x.value) }), {});
  const meiaNoite = agora - (p.hour * 3600 + p.minute * 60 + p.second);

  let mWh = 0, mWh100 = 0;
  for (let i = 0; i < leituras.length - 1; i++) {
    const l = leituras[i];
    if (l.ts < meiaNoite) continue;
    const dt = Math.min(leituras[i + 1].ts - l.ts, 60);
    const mW = (no === 'no1' && l.corrente_ma !== null)
      ? 3.3 * Number(l.corrente_ma)                       // nó 1: corrente medida pelo INA219
      : P_100_MW * (Number(l.led_pct) || 0) / 100;         // restantes: estimado pela intensidade
    mWh += mW * dt / 3600;
    if ((Number(l.led_pct) || 0) > 0) {
      mWh100 += P_100_MW * dt / 3600;                      // só o tempo em que a luz esteve acesa, a 100 %
    }
  }
  return { mWh, poupanca: mWh100 - mWh, mWh100 };
}

// Gráfico das últimas 24 h: LED (%), luz ambiente e presença
function desenharGrafico(leituras, fuso) {
  const sensor = leituras.length ? leituras[0].sensor_luz : null;
  const luz = leituras.map((l) => {
    if (l.luz_raw === null || l.luz_raw === undefined) return null;
    if (sensor === 'digital') return Number(l.luz_raw) === 1 ? 0 : 100;     // escuro = 0, claro = 100
    if (sensor === 'lux') return Number(l.luz_raw);
    return Math.round(Number(l.luz_raw) / 4095 * 100);
  });
  const dados = {
    labels: leituras.map((l) => horaLocal(fuso, l.ts)),
    datasets: [
      { label: 'Presença', data: leituras.map((l) => Number(l.presenca) === 1 ? 100 : 0), stepped: true, fill: true,
        backgroundColor: 'rgba(16, 35, 61, 0.10)', borderWidth: 0, pointRadius: 0 },
      { label: 'LED (%)', data: leituras.map((l) => Number(l.led_pct) || 0), stepped: true,
        borderColor: '#E0A100', backgroundColor: '#E0A100', borderWidth: 2, pointRadius: 0 },
      { label: sensor === 'lux' ? 'Luz ambiente (lx)' : 'Luz ambiente (%)', data: luz, yAxisID: sensor === 'lux' ? 'lux' : 'y',
        borderColor: '#2563A8', backgroundColor: '#2563A8', borderWidth: 2, pointRadius: 0, tension: 0.2 },
    ],
  };
  const escalas = {
    y: { min: 0, max: 100, ticks: { stepSize: 50 } },
    x: { ticks: { maxTicksLimit: 6, maxRotation: 0 } },
  };
  if (sensor === 'lux') escalas.lux = { position: 'right', min: 0, grid: { display: false } };

  if (grafico) grafico.destroy();
  grafico = new Chart($('grafico'), {
    type: 'line',
    data: dados,
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      scales: escalas,
      plugins: { legend: { labels: { boxWidth: 12, font: { family: 'Atkinson Hyperlegible' } } } },
    },
  });
}

async function escolher(no, div) {
  escolhida = { no, div };
  $('det-vazio').hidden = true;
  $('det-conteudo').hidden = false;
  desenharCasas();
  desenharValores();
  if (window.innerWidth <= 900) $('detalhe').scrollIntoView({ behavior: 'smooth' });

  $('det-consumo').textContent = 'A calcular…';
  try {
    const fuso = (casas[no] || {}).fuso;
    const h = await pedir({ o: 'historico', no_id: no, divisao: div });
    const leituras = (h.leituras || []).sort((a, b) => a.ts - b.ts);
    desenharGrafico(leituras, fuso);

    const c = consumoHoje(leituras, no, fuso);
    const pct = c.mWh100 > 0 ? Math.round(c.poupanca / c.mWh100 * 100) : 0;
    $('det-consumo').innerHTML = '';
    $('det-consumo').append(el('strong', '', `${c.mWh.toFixed(1)} mWh`),
      el('span', '', c.mWh100 > 0
        ? ` hoje. No tempo em que a luz esteve acesa, a 100 % seriam ${c.mWh100.toFixed(1)} mWh: poupança de ${c.poupanca.toFixed(1)} mWh (${pct} %).`
        : ' hoje. A luz ainda não acendeu hoje, por isso não há poupança a calcular.'));
  } catch (e) {
    $('det-consumo').textContent = 'Não foi possível obter o histórico.';
  }
}

// ---------- ciclo de atualização ----------
async function atualizar() {
  const estado = $('estado-pagina');
  try {
    pacote = await pedir({ o: 'estado' });
    desenharCasas();
    desenharValores();
    estado.className = 'estado-pagina';
    estado.textContent = 'Atualizado às ' + new Date().toLocaleTimeString('pt-PT');
  } catch (e) {
    estado.className = 'estado-pagina erro';
    estado.textContent = 'Sem ligação ao servidor';
  }
}

async function iniciar() {
  try {
    const r = await pedir({ o: 'nos' });
    for (const n of r.nos || []) casas[n.no_id] = { pais: n.pais, fuso: n.fuso };
  } catch (e) { /* sem país e fuso, o painel funciona na mesma com a hora de Lisboa */ }
  await atualizar();
  setInterval(atualizar, INTERVALO_MS);
}

iniciar();
