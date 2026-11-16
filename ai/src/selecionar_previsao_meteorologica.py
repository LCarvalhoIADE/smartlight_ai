"""
Seleciona uma aquisição meteorológica disponível antes da emissão.

Regras iniciais:
- Margem de 5 minutos antes da emissão.
- Idade máxima de 12 horas, contada até à emissão.
- Mesmo nó, localização, fuso e dia alvo.
- Apenas previsões, nunca meteorologia histórica.
- Escolhe a aquisição elegível mais recente.

Os limites são configuráveis e provisórios.
Este módulo não consulta APIs, não altera ficheiros e não prevê energia.
"""

import argparse
import json
import math
from copy import deepcopy
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ai.src.adquirir_previsao_meteorologica import (
    ENDPOINT,
    HORA_ANTERIOR,
    identificar_no,
    instante_utc,
    planear_periodo,
)
from ai.src.preparar_meteorologia import (
    UNIDADES,
    preparar_meteorologia,
)


