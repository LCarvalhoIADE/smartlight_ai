// SmartLight · dashboard (estado atual + últimas leituras)
'use strict';

const INTERVALO_MS = 15000;
const ESCONDER_S = 86400;   // esconde divisões sem leituras há mais de 24 h

let grafico = null;
let escolhida = null;       // "no2/quarto"
let ultimoPacote = null;

const $ = (id) => document.getElementById(id);

function horaLocal(ts) {
  return new Date(ts * 1000).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function haQuanto(seg) {
  if (seg < 60) return `há ${Math.max(0, Math.round(seg))} s`;
  if (seg < 3600) return `há ${Math.round(seg / 60)} min`;
  if (seg < 86400) return `há ${Math.round(seg / 3600)} h`;
  return `há ${Math.round(seg / 86400)} dias`;
}

function nomeNo(id) {
  const m = /^no(\d+)$/.exec(id);
  return m ? `Nó ${m[1]}` : id;
}

function nomeDiv(d) {
  return d ? d.charAt(0).toUpperCase() + d.slice(1) : '—';
}

// Agrupa as leituras: nó -> divisão -> lista (mais recente primeiro)
function agrupar(leituras, agora) {
  const nos = new Map();
  const ordenadas = [...leituras].sort((a, b) => b.ts - a.ts);
  for (const l of ordenadas) {
    if (!nos.has(l.no_id)) nos.set(l.no_id, new Map());
    const divs = nos.get(l.no_id);
    if (!divs.has(l.divisao)) divs.set(l.divisao, []);
    divs.get(l.divisao).push(l);
  }
  // Esconde as divisões paradas há mais de 24 h, se o nó tiver outras com leituras recentes.
  // Se o nó estiver todo parado, mostra tudo, para se ver que está offline.
  if (agora) {
    for (const divs of nos.values()) {
      const recente = Math.max(...[...divs.values()].map((lista) => lista[0].ts));
      if (agora - recente > ESCONDER_S) continue;
      for (const [div, lista] of divs) {
        if (agora - lista[0].ts > ESCONDER_S) divs.delete(div);
      }
    }
  }
  return new Map([...nos].sort((a, b) => a[0].localeCompare(b[0], 'pt', { numeric: true })));
}

function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

function desenharCartoes(nos, agora, offlineS) {
  const caixa = $('nos');
  caixa.replaceChildren();

  if (nos.size === 0) {
    caixa.append(el('p', 'vazio', 'Ainda não há leituras.'));
    return;
  }

  for (const [no, divs] of nos) {
    const ultima = Math.max(...[...divs.values()].map((l) => l[0].ts));
    const atraso = agora - ultima;
    const online = atraso <= offlineS;
    const primeira = [...divs.values()][0][0];

    const c = el('article', 'cartao no' + (online ? '' : ' offline'));
    const cab = el('div', 'no-cab');
    cab.append(el('h3', '', nomeNo(no)));
    cab.append(el('span', 'pastilha ' + (online ? 'ok' : 'mau'), online ? 'online' : 'offline'));
    c.append(cab);

    const luz = primeira.luz_pct;
    const info = el('p', 'no-info');
    info.textContent = `Luz ambiente: ${luz === null || luz === undefined ? 'sem sensor' : luz + ' %'} · ${haQuanto(atraso)}`;
    c.append(info);

    for (const [div, lista] of divs) {
      const l = lista[0];
      const pres = Number(l.presenca) === 1;
      const led = Number(l.led_pct) || 0;

      const linha = el('button', 'divisao');
      linha.type = 'button';
      linha.title = 'Ver no gráfico';
      if (escolhida === `${no}/${div}`) linha.classList.add('ativa');
      linha.addEventListener('click', () => escolher(`${no}/${div}`));

      const idade = agora - l.ts;
      const parada = idade > offlineS;
      if (parada) linha.classList.add('parada');

      const topo = el('div', 'div-topo');
      topo.append(el('span', 'div-nome', nomeDiv(div)));
      topo.append(el('span', 'pres ' + (!parada && pres ? 'sim' : 'nao'),
        parada ? `sem leituras ${haQuanto(idade)}` : (pres ? 'com presença' : 'vazia')));
      linha.append(topo);

      const barra = el('div', 'barra');
      const cheio = el('div', 'barra-cheia');
      cheio.style.width = led + '%';
      barra.append(cheio);
      linha.append(barra);

      linha.append(el('span', 'div-led', `LED ${led} % · ${l.modo || 'auto'}`));
      c.append(linha);
    }
    caixa.append(c);
  }
}

function atualizarEscolha(nos) {
  const sel = $('escolha');
  const opcoes = [];
  for (const [no, divs] of nos) for (const div of divs.keys()) opcoes.push(`${no}/${div}`);

  if (!escolhida || !opcoes.includes(escolhida)) escolhida = opcoes[0] || null;

  sel.replaceChildren(...opcoes.map((v) => {
    const [no, div] = v.split('/');
    const o = el('option', '', `${nomeNo(no)} · ${nomeDiv(div)}`);
    o.value = v;
    o.selected = v === escolhida;
    return o;
  }));
}

function cores() {
  const s = getComputedStyle(document.documentElement);
  return {
    led: s.getPropertyValue('--led').trim(),
    luz: s.getPropertyValue('--luz').trim(),
    pres: s.getPropertyValue('--pres').trim(),
    texto: s.getPropertyValue('--texto-2').trim(),
    grelha: s.getPropertyValue('--linha').trim(),
  };
}

function desenharGrafico(nos) {
  if (!escolhida || typeof Chart === 'undefined') return;
  const [no, div] = escolhida.split('/');
  const lista = (nos.get(no)?.get(div) || []).slice().reverse(); // mais antiga primeiro

  const etiquetas = lista.map((l) => horaLocal(l.ts));
  const led = lista.map((l) => Number(l.led_pct) || 0);
  const luz = lista.map((l) => (l.luz_pct === null || l.luz_pct === undefined ? null : Number(l.luz_pct)));
  const pres = lista.map((l) => (Number(l.presenca) === 1 ? 100 : 0));
  const c = cores();

  const dados = {
    labels: etiquetas,
    datasets: [
      {
        label: 'Presença', data: pres, stepped: true, fill: true, borderWidth: 0,
        backgroundColor: c.pres, pointRadius: 0, order: 3
      },
      {
        label: 'LED (%)', data: led, stepped: true, borderColor: c.led, backgroundColor: c.led,
        borderWidth: 2, pointRadius: 0, order: 1
      },
      {
        label: 'Luz ambiente (%)', data: luz, borderColor: c.luz, backgroundColor: c.luz,
        borderWidth: 2, pointRadius: 0, tension: 0.3, spanGaps: true, order: 2
      },
    ],
  };

  if (grafico) {
    grafico.data = dados;
    grafico.update('none');
    return;
  }

  grafico = new Chart($('grafico'), {
    type: 'line',
    data: dados,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { min: 0, max: 100, ticks: { color: c.texto, stepSize: 25 }, grid: { color: c.grelha } },
        x: {
          ticks: {
            color: c.texto, maxTicksLimit: window.innerWidth < 600 ? 4 : 7, maxRotation: 0,
            callback(v) { return this.getLabelForValue(v).slice(0, 5); }
          }, grid: { display: false }
        },
      },
      plugins: {
        legend: { labels: { color: c.texto, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) => ctx.dataset.label === 'Presença'
              ? (ctx.parsed.y ? 'Com presença' : 'Sem presença')
              : `${ctx.dataset.label}: ${ctx.parsed.y}`,
          },
        },
      },
    },
  });
}

function escolher(v) {
  escolhida = v;
  if (!ultimoPacote) return;
  const nos = agrupar(ultimoPacote.leituras, ultimoPacote.agora);
  atualizarEscolha(nos);
  desenharCartoes(nos, ultimoPacote.agora, ultimoPacote.offline_s);
  desenharGrafico(nos);
}

function estadoLigacao(ok, texto) {
  const p = $('estado-ligacao');
  p.className = 'pastilha ' + (ok ? 'ok' : 'mau');
  p.textContent = texto;
}

async function atualizar() {
  try {
    const r = await fetch(`dados.php?n=${N_LEITURAS}`, { cache: 'no-store', credentials: 'same-origin' });
    if (r.status === 401) { location.href = 'login.php'; return; }
    const pacote = await r.json();
    if (!r.ok) throw new Error(pacote.erro || `erro ${r.status}`);

    ultimoPacote = pacote;
    const nos = agrupar(pacote.leituras || [], pacote.agora);
    atualizarEscolha(nos);
    desenharCartoes(nos, pacote.agora, pacote.offline_s || 60);
    desenharGrafico(nos);
    estadoLigacao(true, `atualizado às ${horaLocal(pacote.agora)}`);
  } catch (e) {
    estadoLigacao(false, 'sem ligação ao servidor');
    console.error(e);
  }
}

$('escolha').addEventListener('change', (ev) => escolher(ev.target.value));
atualizar();
setInterval(atualizar, INTERVALO_MS);
