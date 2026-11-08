<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SmartLight · Dashboard</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="topo">
  <h1>SmartLight</h1>
  <span id="estado-ligacao" class="pastilha">a carregar…</span>
</header>
<main>
  <h2>Estado atual</h2>
  <div id="nos" class="grelha"></div>

  <h2>Últimas leituras</h2>
  <select id="escolha" aria-label="Divisão a mostrar no gráfico"></select>
  <div style="position: relative; height: 260px;"><canvas id="grafico"></canvas></div>
</main>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="assets/cartoes.js"></script>
</body>
</html>