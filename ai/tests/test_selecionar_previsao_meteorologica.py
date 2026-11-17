"""Testes com aquisições fictícias, sem rede e sem dados reais."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ai.src.adquirir_previsao_meteorologica import adquirir
from ai.src.preparar_meteorologia import UNIDADES
from ai.src.selecionar_previsao_meteorologica import selecionar


@pytest.fixture
def historico(): 
    """Metadados fictícios para uma instalação de teste."""
    return {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": "Europe/Lisbon",
        }
    }

