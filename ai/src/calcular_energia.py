import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


CAMPOS_SAIDA = (
    "no_id",
    "divisao",
    "hora_utc",
    "energia_mWh",
    "energia_Wh",
    "segundos_integrados",
    "segundos_excluidos",
    "cobertura_proporcao",
    "tensao_assumida_v",
    "limite_intervalo_segundos",
    "origem_energia",
)

