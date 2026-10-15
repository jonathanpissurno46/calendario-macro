#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualiza datos.json para el Calendario Economico Macro.

  1. Descarga el calendario publico de la semana (ForexFactory).
  2. Si hay una clave de API configurada, descarga tambien los VALORES REALES
     ya publicados y los fusiona con el calendario base.
  3. Escribe datos.json en la raiz del repositorio.

Claves (se leen de variables de entorno, nunca van escritas en el codigo):
    FMP_API_KEY        -> financialmodelingprep.com   (se prueba primero)
    FINNHUB_API_KEY    -> finnhub.io
Si no hay ninguna, se guarda el calendario base sin valores reales y ya esta:
la aplicacion lo detecta y sigue funcionando con la prevision.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = "Mozilla/5.0 (compatible; CalendarioMacro/1.0)"

# Codigo de pais -> divisa (para emparejar las dos fuentes)
PAIS_A_DIVISA = {
    "US": "USD", "EU": "EUR", "EA": "EUR", "EZ": "EUR", "DE": "EUR", "FR": "EUR",
    "IT": "EUR", "ES": "EUR", "GB": "GBP", "UK": "GBP", "JP": "JPY", "CA": "CAD",
    "AU": "AUD", "CN": "CNY", "CH": "CHF", "NZ": "NZD",
}


def bajar_json(url, cabeceras=None):
    pet = urllib.request.Request(url, headers=cabeceras or {"User-Agent": UA})
    with urllib.request.urlopen(pet, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# Palabras que no ayudan a distinguir un evento de otro
RUIDO = {"speaks", "speech", "member", "statement", "press", "conference", "report",
         "the", "of", "and", "a", "an", "in", "on", "for", "to", "s", "initial"}
# Distintivos que DEBEN coincidir en las dos fuentes (si uno lo tiene, el otro tambien)
CRITICOS = {"core", "ex", "prelim", "preliminary", "final", "advance", "flash",
            "revised", "continuing", "mom", "yoy", "qoq"}
# Como llama cada fuente a lo mismo
SINONIMOS = {"yy": "yoy", "yoy": "yoy", "mm": "mom", "mom": "mom", "qq": "qoq", "qoq": "qoq",
             "jobless": "unemployment", "philadelphia": "philly", "nonfarm": "nfp",
             "non": "nfp", "farm": "nfp", "mom": "mom", "3m": "3m"}


def normaliza(texto):
    """Pasa 'y/y' a 'yoy', 'm/m' a 'mom'... para que las dos fuentes se entiendan."""
    t = str(texto or "").lower()
    t = re.sub(r"\by\s*/\s*y\b", " yoy ", t)
    t = re.sub(r"\bm\s*/\s*m\b", " mom ", t)
    t = re.sub(r"\bq\s*/\s*q\b", " qoq ", t)
    t = re.sub(r"\by/y\b|\bm/m\b|\bq/q\b", " ", t)
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def palabras(titulo):
    salida = set()
    for t in normaliza(titulo):
        t = SINONIMOS.get(t, t)
        if t in RUIDO:
            continue
        salida.add(t)
    return salida


def encajan(titulo_feed, titulo_api):
    """Devuelve una puntuacion de 0 a 1. 0 = no son el mismo evento."""
    a, b = palabras(titulo_feed), palabras(titulo_api)
    if not a or not b:
        return 0.0
    if (a & CRITICOS) != (b & CRITICOS):
        return 0.0                      # core vs no-core, preliminar vs final...
    comunes = a & b
    if not comunes:
        return 0.0
    cob_base = len(comunes) / len(a)
    cob_api = len(comunes) / len(b)
    if cob_base < 0.6 or cob_api < 0.5:
        return 0.0                      # no se parecen lo suficiente
    return round((cob_base + cob_api) / 2, 3)


def a_numero(valor):
    """Convierte '215K', '1.2%', '-0.1%' o 3.7 al numero que usa la aplicacion."""
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
    """20500 -> '20.5K' (mismo valor, más legible), solo si es exacto."""
    for corte, sufijo in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(numero) >= corte:
            reducido = round(numero / corte, 1)
            if abs(reducido * corte - numero) < 1e-6:
                return ("%g" % reducido) + sufijo
            return "%g" % numero
    return "%g" % numero


def formatea(valor, unidad):
    """Devuelve el valor real como texto, con el mismo estilo que el feed base."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, str):
        limpio = valor.strip()
        if not limpio:
            return ""
        numero = a_numero(limpio)
        if numero is None:
            return limpio
    else:
        numero = a_numero(valor)
        if numero is None:
            return ""
    unidad = (unidad or "").strip()
    if unidad == "%":
        return ("%g" % numero) + "%"
    if unidad.upper() in ("K", "M", "B"):
        # Si ya viene escalado (20500 con unidad K) no se le vuelve a añadir
        return ("%g" % numero) + unidad.upper() if abs(numero) < 1000 else bonito(numero)
    return bonito(numero)


def valores_fmp(clave, desde, hasta):
    url = ("https://financialmodelingprep.com/api/v3/economic_calendar"
           "?from=%s&to=%s&apikey=%s" % (desde, hasta, urllib.parse.quote(clave)))
    datos = bajar_json(url)
    if isinstance(datos, dict) and datos.get("Error Message"):
        raise RuntimeError(datos["Error Message"])
    salida = []
    for x in datos if isinstance(datos, list) else []:
        salida.append({
            "divisa": (x.get("currency") or PAIS_A_DIVISA.get(str(x.get("country", "")).upper(), "")).upper(),
            "fecha": str(x.get("date", ""))[:10],
            "titulo": x.get("event") or x.get("title") or "",
            "actual": x.get("actual"),
            "unidad": x.get("unit") or "",
        })
    return salida


def valores_finnhub(clave, desde, hasta):
    url = ("https://finnhub.io/api/v1/calendar/economic"
           "?from=%s&to=%s&token=%s" % (desde, hasta, urllib.parse.quote(clave)))
    datos = bajar_json(url)
    lista = datos.get("economicCalendar", []) if isinstance(datos, dict) else []
    salida = []
    for x in lista:
        pais = str(x.get("country", "")).upper()
        salida.append({
            "divisa": PAIS_A_DIVISA.get(pais, pais),
            "fecha": str(x.get("time", ""))[:10],
            "titulo": x.get("event") or "",
            "actual": x.get("actual"),
            "unidad": x.get("unit") or "",
        })
    return salida


def fusiona(base, reales):
    """Copia el valor real al evento que le corresponde del calendario base."""
    indice = {}
    for r in reales:
        if r["divisa"] and r["fecha"]:
            indice.setdefault((r["divisa"], r["fecha"]), []).append(r)

    puestos = 0
    descartados = 0
    for evento in base:
        divisa = str(evento.get("country", "")).upper()
        fecha = str(evento.get("date", ""))[:10]
        candidatos = []
        for desplazamiento in (0, -1, 1):     # el feed va en hora de Nueva York y la API puede ir en UTC
            if desplazamiento == 0:
                dia = fecha
            else:
                try:
                    from datetime import date, timedelta
                    d = date.fromisoformat(fecha) + timedelta(days=desplazamiento)
                    dia = d.isoformat()
                except ValueError:
                    continue
            candidatos.extend(indice.get((divisa, dia), []))
        if not candidatos:
            continue
        # Solo se acepta si el nombre del evento coincide de verdad
        puntuados = []
        for c in candidatos:
            nota = encajan(evento.get("title"), c["titulo"])
            if nota > 0:
                puntuados.append((nota, c))
        if not puntuados:
            continue
        puntuados.sort(key=lambda x: -x[0])
        if len(puntuados) > 1 and puntuados[0][0] == puntuados[1][0] and \
           formatea(puntuados[0][1]["actual"], puntuados[0][1]["unidad"]) != \
           formatea(puntuados[1][1]["actual"], puntuados[1][1]["unidad"]):
            descartados += 1
            continue                     # empate ambiguo: mejor no arriesgar
        mejor = puntuados[0][1]
        texto = formatea(mejor["actual"], mejor["unidad"])
        if not texto:
            continue
        real = a_numero(texto)
        previsto = a_numero(evento.get("forecast"))
        # Si las escalas no cuadran (p. ej. 20500 frente a 19.6K), mejor no inventar
        if real is not None and previsto not in (None, 0):
            if not (0.01 <= abs(real / previsto) <= 100):
                descartados += 1
                continue
        evento["actual"] = texto
        puestos += 1
    if descartados:
        print("Descartados por dudas de emparejamiento o de escala: %d" % descartados)
    return puestos


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = os.path.join(raiz, "datos.json")

    base = bajar_json(FF_URL)
    if not isinstance(base, list) or not base:
        print("ERROR: el feed base no devolvio eventos. No se toca datos.json.")
        return 1

    fechas = sorted({str(x.get("date", ""))[:10] for x in base if x.get("date")})
    desde, hasta = fechas[0], fechas[-1]

    clave_fmp = os.environ.get("FMP_API_KEY", "").strip()
    clave_fh = os.environ.get("FINNHUB_API_KEY", "").strip()

    reales, origen = [], "ForexFactory"
    fallo = ""
    if clave_fmp or clave_fh:
        try:
            if clave_fmp:
                reales = valores_fmp(clave_fmp, desde, hasta)
                origen = "ForexFactory + Financial Modeling Prep"
            else:
                reales = valores_finnhub(clave_fh, desde, hasta)
                origen = "ForexFactory + Finnhub"
            print("API de valores reales: %d registros descargados." % len(reales))
            if not reales:
                fallo = "La API respondio pero sin registros en esas fechas."
        except Exception as err:                      # noqa: BLE001
            fallo = str(err)
            print("AVISO: fallo la API de valores reales (%s)." % err)
            print("       Se guarda el calendario base; la app seguira funcionando.")
            reales = []
    else:
        print("Sin clave de API configurada: se guarda el calendario base.")

    def limpia(texto):
        """Quita del mensaje cualquier cosa que parezca una clave."""
        return re.sub(r"[A-Za-z0-9_\-]{18,}", "***", str(texto))[:200]

    puestos = fusiona(base, reales) if reales else 0
    print("Valores reales fusionados: %d de %d eventos." % (puestos, len(base)))

    clave = clave_fmp or clave_fh
    paquete = {
        "origen": origen if puestos else "ForexFactory (sin valores reales)",
        "conValoresReales": puestos,
        "diagnostico": {
            "claveDetectada": "FMP_API_KEY" if clave_fmp else ("FINNHUB_API_KEY" if clave_fh else "ninguna"),
            "longitudClave": len(clave),
            "apiRespondio": bool(reales),
            "registrosApi": len(reales),
            "mensaje": limpia(fallo) if fallo else "",
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
    igual = isinstance(anterior, dict) and all(
        anterior.get(k) == v for k, v in paquete.items()
    )
    paquete["actualizado"] = (anterior.get("actualizado") if igual and anterior.get("actualizado")
                              else datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))

    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(paquete, fh, ensure_ascii=False, separators=(",", ":"))
    print("Escrito %s (%d eventos)." % (destino, len(base)))
    print("DIAGNOSTICO -> clave: %s | api respondio: %s | registros: %d | mensaje: %s"
          % (paquete["diagnostico"]["claveDetectada"],
             paquete["diagnostico"]["apiRespondio"],
             paquete["diagnostico"]["registrosApi"],
             paquete["diagnostico"]["mensaje"] or "(ninguno)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
