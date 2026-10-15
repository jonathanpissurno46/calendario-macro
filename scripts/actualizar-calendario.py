#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualiza datos.json para el Calendario Economico Macro.

  1. Descarga el calendario economico publico de TradingView, que YA INCLUYE
     los valores reales publicados (actual), la prevision y el dato previo.
     No necesita ninguna clave ni registro.
  2. Si TradingView fallara, usa el feed publico de ForexFactory como respaldo
     (en ese caso no habria valores reales, solo previsiones).
  3. Escribe datos.json en la raiz del repositorio.

No usa claves de API de ningun tipo.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TV_URL = ("https://economic-calendar.tradingview.com/events"
          "?from={desde}T00:00:00.000Z&to={hasta}T23:59:59.000Z"
          "&countries=US,EU,GB,JP,CA,AU,CN,CH,NZ,DE,FR,IT,ES")
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = "Mozilla/5.0 (compatible; CalendarioMacro/1.0)"

# Solo se publican los eventos de importancia media y alta (mas los festivos):
# el calendario queda limpio y sin subastas ni indices menores.
IMPORTANCIA_MINIMA = 0


def bajar_json(url, cabeceras=None):
    cab = {"User-Agent": UA}
    if cabeceras:
        cab.update(cabeceras)
    pet = urllib.request.Request(url, headers=cab)
    with urllib.request.urlopen(pet, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def a_numero(valor):
    """Convierte '3.7', '-39.3K' o 0.3 al numero que usa la aplicacion."""
    if valor is None:
        return None
    texto = str(valor).replace(",", "").replace("%", "").replace("+", "").strip()
    if not texto:
        return None
    multiplicador = 1
    ultimo = texto[-1:].upper()
    if ultimo in ("K", "M", "B"):
        multiplicador = {"K": 1e3, "M": 1e6, "B": 1e9}[ultimo]
        texto = texto[:-1]
    try:
        return float(texto) * multiplicador
    except (TypeError, ValueError):
        return None


def bonito(numero):
    """3990000 -> '3.99M'; -39300 -> '-39.3K'. Solo si la conversion es exacta."""
    for corte, sufijo in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(numero) >= corte:
            reducido = numero / corte
            for decimales in (1, 2, 3):
                if abs(round(reducido, decimales) * corte - numero) < 1e-6:
                    return ("%g" % round(reducido, decimales)) + sufijo
            return "%g" % numero
    return "%g" % numero


# Solo se marca con "%" lo que lleva periodo (YoY/MoM/QoQ) o la palabra "Rate".
# Asi un nivel de indice ("CPI" = 336.94, "Business Confidence" = -13) no se
# confunde con un porcentaje.
RE_PORCENTAJE = re.compile(r"\b(yoy|mom|qoq|rate)\b", re.I)


def es_porcentaje(titulo):
    return bool(RE_PORCENTAJE.search(titulo or ""))


def texto_valor(evento, campo):
    """Devuelve el valor como texto legible. Devuelve '' si no hay dato."""
    valor = evento.get(campo)
    if valor is None or valor == "":
        return ""
    bruto = evento.get(campo + "Raw")
    crudo = a_numero(bruto) if bruto is not None else None
    numero = a_numero(valor)
    if numero is None:
        return str(valor).strip()
    # Si el valor bruto esta escalado (3990000 frente a 3.99), no es un porcentaje
    escalado = crudo is not None and abs(crudo - numero) > 1e-9
    titulo = str(evento.get("title") or evento.get("indicator") or "")
    unidad = "%" if (not escalado and es_porcentaje(titulo)) else ""
    return bonito(numero) + unidad


def eventos_tradingview(desde, hasta):
    """Lista de eventos desde el calendario publico de TradingView."""
    datos = bajar_json(
        TV_URL.format(desde=desde, hasta=hasta),
        {"Origin": "https://www.tradingview.com",
         "Referer": "https://www.tradingview.com/economic-calendar/"},
    )
    lista = datos.get("result") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or not lista:
        raise RuntimeError("TradingView no devolvio eventos")

    salida = []
    for x in lista:
        divisa = str(x.get("currency") or "").upper()
        fecha = str(x.get("date") or "")
        titulo = str(x.get("title") or x.get("indicator") or "").strip()
        if not divisa or not fecha or not titulo:
            continue
        try:
            importancia = int(x.get("importance"))
        except (TypeError, ValueError):
            importancia = -1
        es_festivo = "holiday" in titulo.lower()
        if importancia < IMPORTANCIA_MINIMA and not es_festivo:
            continue

        momento = fecha
        todoeldia = False
        if es_festivo:
            momento = fecha[:10] + "T12:00:00Z"      # los festivos, anclados a mediodia
            todoeldia = True

        evento = {
            "title": titulo,
            "country": divisa,
            "date": momento,
            "impact": "Holiday" if es_festivo else ("High" if importancia >= 1
                                                    else "Medium" if importancia == 0 else "Low"),
            "actual": texto_valor(x, "actual"),
            "forecast": texto_valor(x, "forecast"),
            "previous": texto_valor(x, "previous"),
        }
        if todoeldia:
            evento["allDay"] = True
        salida.append(evento)
    if not salida:
        raise RuntimeError("TradingView no devolvio eventos utiles")
    return salida


def eventos_forex():
    """Respaldo: feed publico de ForexFactory (sin valores reales)."""
    base = bajar_json(FF_URL)
    if not isinstance(base, list) or not base:
        raise RuntimeError("ForexFactory no devolvio eventos")
    return base


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = os.path.join(raiz, "datos.json")

    hoy = datetime.now(timezone.utc).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    desde, hasta = lunes.isoformat(), domingo.isoformat()

    origen = ""
    error_tv = ""
    try:
        base = eventos_tradingview(desde, hasta)
        origen = "TradingView (calendario publico, con valores reales)"
        print("TradingView: %d eventos descargados." % len(base))
    except Exception as err:                          # noqa: BLE001
        error_tv = str(err)
        print("AVISO: TradingView fallo (%s). Se intenta ForexFactory." % err)
        try:
            base = eventos_forex()
            origen = "ForexFactory (solo previsiones, sin valores reales)"
            print("ForexFactory: %d eventos descargados." % len(base))
        except Exception as err2:                     # noqa: BLE001
            print("ERROR: tampoco se pudo usar ForexFactory (%s)." % err2)
            print("       No se toca datos.json: los datos anteriores siguen intactos.")
            return 1

    con_real = sum(1 for e in base if e.get("actual"))
    print("Eventos con valor real publicado: %d de %d." % (con_real, len(base)))

    paquete = {
        "origen": origen,
        "conValoresReales": con_real,
        "diagnostico": {
            "fuente": "TradingView" if origen.startswith("TradingView") else "ForexFactory",
            "eventos": len(base),
            "conValorReal": con_real,
            "rango": desde + " a " + hasta,
            "avisoTradingView": re.sub(r"[A-Za-z0-9_\-]{18,}", "***", error_tv)[:200] if error_tv else "",
        },
        "eventos": base,
    }

    # Si nada ha cambiado, se conserva la fecha anterior para no crear un commit cada 10 minutos
    anterior = {}
    if os.path.exists(destino):
        try:
            with open(destino, encoding="utf-8") as fh:
                anterior = json.load(fh)
        except Exception:                             # noqa: BLE001
            anterior = {}
    igual = isinstance(anterior, dict) and all(anterior.get(k) == v for k, v in paquete.items())
    paquete["actualizado"] = (
        anterior.get("actualizado") if igual and anterior.get("actualizado")
        else datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )

    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(paquete, fh, ensure_ascii=False, separators=(",", ":"))
    print("Escrito %s (%d eventos, %d con valor real)." % (destino, len(base), con_real))
    return 0


if __name__ == "__main__":
    sys.exit(main())
