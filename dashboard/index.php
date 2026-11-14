<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SmartLight · Painel das casas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

<header class="topo">
  <div class="marca">
    <!-- Logótipo: lâmpada com sinal de rede, simplificado do logótipo do projeto -->
    <svg class="logo" viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 6c-11 0-19 8-19 18 0 7 4 11 7 15 2 3 3 5 3 8h18c0-3 1-5 3-8 3-4 7-8 7-15 0-10-8-18-19-18z"
            fill="#F2A33A" stroke="#1E2A3A" stroke-width="3.5" stroke-linejoin="round"/>
      <path d="M24 21a12 12 0 0 1 16 0M27 25a7 7 0 0 1 10 0" fill="none" stroke="#FFFDF8" stroke-width="3" stroke-linecap="round"/>
      <circle cx="32" cy="29" r="2.2" fill="#FFFDF8"/>
      <rect x="23" y="49" width="18" height="5" rx="2.5" fill="#1F8A84" stroke="#1E2A3A" stroke-width="2.5"/>
      <rect x="25" y="55" width="14" height="4" rx="2" fill="#1F8A84" stroke="#1E2A3A" stroke-width="2.5"/>
      <path d="M53 14a14 14 0 0 1 0 18M57 9a20 20 0 0 1 0 28" fill="none" stroke="#1F8A84" stroke-width="3" stroke-linecap="round"/>
    </svg>
    <div>
      <h1>SmartLight</h1>
      <p class="sub">Painel das casas</p>
    </div>
  </div>
  <p id="estado-pagina" class="estado-pagina">A carregar…</p>
</header>

<main class="layout">
  <!-- Plantas das casas, desenhadas pelo painel.js -->
  <section id="casas" class="casas" aria-label="Casas"></section>

  <!-- Detalhe da divisão escolhida -->
  <aside id="detalhe" class="detalhe" aria-live="polite">
    <p id="det-vazio" class="det-vazio">Escolha uma divisão na planta para ver o detalhe.</p>
    <div id="det-conteudo" hidden>
      <p id="det-casa" class="det-casa"></p>
      <h2 id="det-titulo"></h2>
      <dl id="det-valores" class="valores"></dl>

      <h3>Últimas 24 horas</h3>
      <div class="caixa-grafico"><canvas id="grafico"></canvas></div>

      <h3>Consumo de hoje</h3>
      <p id="det-consumo" class="consumo">A calcular…</p>
    </div>
  </aside>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="assets/painel.js"></script>
</body>
</html>
