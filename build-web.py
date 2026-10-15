#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera la carpeta `calendario-web/` lista para subir a cualquier hosting
(Netlify, GitHub Pages, Cloudflare Pages, Vercel...).

Uso:  python3 build-web.py
      (o el python del runtime DSH si el del sistema no tiene Pillow)

Reproduce el calendario como app web instalable (PWA):
  index.html              -> la aplicación
  manifest.webmanifest    -> datos de la app (nombre, iconos, colores)
  sw.js                   -> service worker (funciona sin conexión)
  icon-192.png / icon-512.png / apple-touch-icon.png / favicon.ico
  LEEME.txt               -> instrucciones de publicación
"""
import base64
import io
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "calendario-economico.html")
OUT = os.path.join(BASE, "calendario-web")

PWA_HEAD = """<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0e1117">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Calendario Macro">
<meta name="description" content="Calendario económico con la dirección esperada del precio para DÓLAR, EUR, GBP, NQ, ES, ORO y WTI.">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
"""

PWA_TAIL = """
<script>
/* La app instalable sólo se registra cuando se sirve por web (https o localhost). */
if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js').catch(function(){});
  });
}
</script>
"""

MANIFEST = """{
  "name": "Calendario Económico Macro",
  "short_name": "Calendario Macro",
  "description": "Calendario económico con la dirección esperada del precio para DÓLAR, EUR, GBP, NQ, ES, ORO y WTI.",
  "start_url": "./index.html",
  "scope": "./",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#0e1117",
  "theme_color": "#0e1117",
  "lang": "es",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
"""

SW = """/* Service worker del Calendario Económico Macro.
   Estrategia: red primero para el documento (así recibes las actualizaciones),
   caché primero para iconos y manifiesto. Funciona sin conexión. */
const CACHE = 'calendario-macro-v2';
const ASSETS = ['./', './index.html', './manifest.webmanifest',
                './icon-192.png', './icon-512.png', './apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  const esDocumento = req.mode === 'navigate' ||
                      url.pathname.endsWith('/') ||
                      url.pathname.endsWith('index.html');
  /* datos.json cambia a diario: siempre se intenta traer la versión nueva */
  const esDatos = url.pathname.endsWith('datos.json');

  if (esDocumento || esDatos) {
    e.respondWith(
      fetch(req)
        .then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); return r; })
        .catch(() => caches.match(esDatos ? req : './index.html'))
    );
    return;
  }
  e.respondWith(
    caches.match(req).then(r => r || fetch(req).then(res => {
      const c = res.clone();
      caches.open(CACHE).then(x => x.put(req, c));
      return res;
    }))
  );
});
"""


HEADERS = """/index.html
  Cache-Control: public, max-age=0, must-revalidate
/sw.js
  Cache-Control: public, max-age=0, must-revalidate
/manifest.webmanifest
  Cache-Control: public, max-age=3600
/*.png
  Cache-Control: public, max-age=604800
"""

LEEME = """CALENDARIO ECONÓMICO MACRO — paquete listo para publicar
=========================================================

Qué hay en esta carpeta
-----------------------
  index.html            La aplicación (todo va dentro, no necesita internet).
  manifest.webmanifest  Metadatos para instalarla en el móvil como una app.
  sw.js                 Service worker: una vez cargada, funciona sin conexión.
  icon-192.png          Icono para Android / escritorio.
  icon-512.png          Icono grande.
  apple-touch-icon.png  Icono para iPhone/iPad.
  favicon.ico           Icono de la pestaña del navegador.
  _headers              Reglas de caché (sólo Netlify / Cloudflare; se ignora en GitHub).
  .nojekyll             Necesario en GitHub Pages para que sirva todo tal cual.
  LEEME.txt             Este archivo.

IMPORTANTE: sube el CONTENIDO de esta carpeta, no la carpeta con un nivel
de más. El archivo index.html tiene que quedar en la RAÍZ del sitio.


=========================================================
OPCIÓN A — NETLIFY DROP  (la más fácil: 30 segundos, sin cuenta)
=========================================================
  1. Abre  https://app.netlify.com/drop
  2. Arrastra el CONTENIDO de esta carpeta (o la carpeta entera) a la zona
     de "drag & drop".
  3. En segundos te da una dirección tipo  https://algo-random.netlify.app
     Ya funciona, con HTTPS.
  4. Si creas una cuenta gratuita, conservas el sitio y le cambias el nombre.
  Para actualizar: vuelve a arrastrar el contenido encima del sitio.


=========================================================
OPCIÓN B — GITHUB PAGES SIN USAR EL TERMINAL  (recomendado si quieres GitHub)
=========================================================
  1. Crea un repositorio PÚBLICO en  https://github.com/new
     Nombre: calendario-macro    |    NO marques "Add a README".
     Pulsa "Create repository".
  2. En la página del repositorio vacío verás un enlace que dice
     "uploading an existing file". Púlsalo.
     (También vale: https://github.com/TUUSUARIO/calendario-macro/upload/main)
  3. Abre esta carpeta en el Finder y SELECCIONA TODOS LOS ARCHIVOS
     (Cmd + A) y arrástralos a la zona de subida del navegador.
     Ojo: selecciona los archivos, NO la carpeta contenedora.
  4. Abajo pulsa "Commit changes".
  5. En el repositorio:  Settings > Pages
        Source: Deploy from a branch
        Branch: main   /   carpeta: / (root)   >  Save
  6. Espera 1-2 minutos. Tu calendario estará en:
        https://TUUSUARIO.github.io/calendario-macro/
  Para actualizar: repite los pasos 2-4 subiendo los archivos nuevos.


=========================================================
OPCIÓN B2 — GITHUB PAGES USANDO EL TERMINAL
=========================================================
  Sólo si te manejas con la Terminal. Necesitarás un token de GitHub
  (GitHub ya no acepta la contraseña de la cuenta para subir código):
    1. https://github.com/settings/tokens  >  Generate new token (classic)
       Marca el permiso "repo" y genera el token. Cópialo.
    2. En la Terminal:

         cd "RUTA/DE/ESTA/CARPETA"
         git init
         git add .
         git commit -m "Calendario economico"
         git branch -M main
         git remote add origin https://github.com/TUUSUARIO/calendario-macro.git
         git push -u origin main

       Cuando pida usuario: tu nombre de usuario de GitHub.
       Cuando pida contraseña: PEGA EL TOKEN (no verás nada al pegarlo, es normal).
    3. Activa Pages como en el paso 5 de la opción B.


=========================================================
OPCIÓN C — CLOUDFLARE PAGES
=========================================================
  1. https://pages.cloudflare.com  >  cuenta gratuita.
  2. "Upload assets" y sube el contenido de esta carpeta.
  3. Te da una URL  https://algo.pages.dev


=========================================================
OPCIÓN D — SÓLO EN TU RED LOCAL (sin publicar en internet)
=========================================================
  En la Terminal, dentro de esta carpeta:
        python3 -m http.server 8000
  Y desde el móvil, en la misma wifi:
        http://IP-DEL-ORDENADOR:8000
  (La IP la ves con:  ipconfig getifaddr en0 )


=========================================================
INSTALARLA EN EL MÓVIL COMO SI FUERA UNA APP
=========================================================
  iPhone/iPad (Safari):  Compartir  >  "Añadir a pantalla de inicio"
  Android (Chrome):      menú de tres puntos  >  "Instalar aplicación"
  Se abre a pantalla completa y funciona sin conexión.


=========================================================
SOBRE TUS DATOS
=========================================================
  Lo que guardas (tus eventos propios, los datos reales que introduces con el
  botón "Introducir el dato real" y los filtros) se guarda en el navegador DE
  CADA DISPOSITIVO, no en el servidor. El servidor sólo entrega la aplicación,
  que es estática y no almacena nada.

  Para pasar tus datos de un dispositivo a otro usa los botones de la barra:
    Copia      -> descarga un archivo calendario-copia.json
    Restaurar  -> en el otro dispositivo, carga ese archivo

Requisitos: ninguno. Es un sitio estático: no necesita base de datos,
ni PHP, ni Node en el servidor. Cualquier hosting estático sirve.
"""


ROBOT_INTRO = """


=========================================================
QUE SE ACTUALICE SOLO  (robot de GitHub, opcional)
=========================================================
Tu web puede descargarse el calendario sola cada 10 minutos. Asi no tienes que
volver a subir nada cuando cambien los eventos. Se instala UNA sola vez:

  1. En tu repositorio pulsa   Add file  >  Create new file
  2. En el nombre del archivo escribe EXACTAMENTE esto (las barras crean las
     carpetas solas):

         .github/workflows/actualizar-calendario.yml

  3. Pega el contenido que tienes aqui abajo, entre las lineas PEGIN y FIN.
  4. Abajo pulsa   Commit changes.
  5. Ve a la pestana "Actions" de tu repositorio, entra en
     "Actualizar calendario" y pulsa "Run workflow" para probarlo.
  6. En un minuto aparecera el archivo datos.json en el repositorio y tu web
     mostrara el chip verde  EN VIVO.

Si el robot falla con un error de permisos:
     Settings > Actions > General > Workflow permissions
     marca "Read and write permissions" y guarda.

Mientras el robot no este instalado, o si algun dia falla, el calendario
sigue funcionando con la version curada que va dentro de la aplicacion.


--------------------- PEGIN (copia desde aqui) ---------------------
"""
ROBOT_FIN = """
---------------------- FIN (copia hasta aqui) -----------------------


Que hace el robot exactamente
-----------------------------
  - Cada 10 minutos pide el calendario publico a nfs.faireconomy.media
  - Comprueba que la respuesta sea valida (si no, no toca nada)
  - Si hay cambios, hace un commit automatico con datos.json
  - Tu pagina lee ese datos.json de tu propio dominio, asi que no hay
    problemas de permisos del navegador (CORS)

  El feed cubre la SEMANA EN CURSO, de lunes a domingo. En la aplicacion
  puedes alternar en "Fuente" entre los datos en vivo y tu calendario curado.

Cuanto tarda en verse un dato nuevo
-----------------------------------
  Publicacion oficial  ->  feed publico      : segundos o pocos minutos
  feed publico         ->  robot de GitHub   : hasta 10 minutos (se ejecuta
                                               cada 10 min; GitHub puede
                                               retrasarlo algo mas si hay carga)
  robot                ->  tu pantalla       : la app consulta sola cada 3 min,
                                               y siempre al abrirla o al volver
                                               a la pestana

  Es decir: entre que sale el dato y lo ves pasan, en el mejor de los casos,
  2-3 minutos, y en el peor 10-15. El boton de refresco (el circulito junto al
  chip verde) fuerza la consulta en el momento. Para el segundo exacto de la
  publicacion usa tu plataforma de trading: aqui la ventaja es saber la
  DIRECCION de cada activo, no cazar el tick.
"""


# ----------------------------------------------------------------------
#  Iconos
# ----------------------------------------------------------------------
def make_icon(size):
    from PIL import Image, ImageDraw

    S = size * 4  # supersampling para bordes suaves
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def rr(box, r, fill=None, outline=None, w=1):
        d.rounded_rectangle([c * 4 for c in box], radius=r * 4, fill=fill,
                            outline=outline, width=w * 4)

    # fondo
    rr((0, 0, size, size), int(size * 0.22), fill=(14, 17, 23, 255))

    # tarjeta del calendario
    m = size * 0.16
    rr((m, m * 1.15, size - m, size - m * 0.95), int(size * 0.09),
       fill=(27, 36, 49, 255), outline=(59, 130, 246, 255), w=max(2, size // 90))

    # cabecera azul
    hh = size * 0.135
    rr((m, m * 1.15, size - m, m * 1.15 + hh), int(size * 0.09), fill=(59, 130, 246, 255))
    d.rectangle([m * 4, (m * 1.15 + hh * 0.55) * 4, (size - m) * 4, (m * 1.15 + hh) * 4],
                fill=(59, 130, 246, 255))

    # anillas del calendario
    for cx in (size * 0.34, size * 0.66):
        d.rounded_rectangle([(cx - size * 0.028) * 4, (m * 0.86) * 4,
                             (cx + size * 0.028) * 4, (m * 1.32) * 4],
                            radius=size * 0.028 * 4, fill=(232, 238, 246, 255))

    # filas de eventos con colores de impacto
    colores = [(255, 77, 77), (255, 159, 46), (242, 211, 60)]
    y0 = m * 1.15 + hh + size * 0.052
    alto = size * 0.062
    paso = size * 0.118
    for i, col in enumerate(colores):
        y = y0 + i * paso
        rr((m + size * 0.062, y, m + size * 0.062 + alto, y + alto),
           int(size * 0.016), fill=col + (255,))
        rr((m + size * 0.062 + alto * 1.7, y + alto * 0.22,
            size - m - size * 0.062, y + alto * 0.78),
           int(size * 0.014), fill=(63, 79, 100, 255))

    return img.resize((size, size), Image.LANCZOS)


def main():
    if not os.path.exists(SRC):
        sys.exit("No encuentro calendario-economico.html junto a este script.")

    os.makedirs(OUT, exist_ok=True)

    html = io.open(SRC, encoding="utf-8").read()
    if "</head>" not in html or "</body>" not in html:
        sys.exit("El HTML de origen no tiene la estructura esperada.")
    html = html.replace("</head>", PWA_HEAD + "</head>", 1)
    html = html.replace("</body>", PWA_TAIL + "</body>", 1)
    io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)

    io.open(os.path.join(OUT, "manifest.webmanifest"), "w", encoding="utf-8").write(MANIFEST)
    io.open(os.path.join(OUT, "sw.js"), "w", encoding="utf-8").write(SW)
    io.open(os.path.join(OUT, "LEEME.txt"), "w", encoding="utf-8").write(LEEME)
    io.open(os.path.join(OUT, "_headers"), "w", encoding="utf-8").write(HEADERS)
    # GitHub Pages: evita que Jekyll procese el sitio (y que ignore archivos con "_")
    io.open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8").write("")

    try:
        make_icon(192).save(os.path.join(OUT, "icon-192.png"))
        make_icon(512).save(os.path.join(OUT, "icon-512.png"))
        make_icon(180).save(os.path.join(OUT, "apple-touch-icon.png"))
        make_icon(64).save(os.path.join(OUT, "favicon.ico"), sizes=[(64, 64)])
        iconos = "iconos generados"
    except Exception as e:  # sin Pillow seguimos, sólo faltarán los iconos
        iconos = "AVISO: no se pudieron generar los iconos (%s)" % e

    # Añade al LEEME las instrucciones del robot + el propio archivo a copiar
    try:
        yml = io.open(os.path.join(OUT, ".github/workflows/actualizar-calendario.yml"),
                      encoding="utf-8").read()
    except Exception:
        yml = "(no se encontro el archivo del robot)"
    bloque = ROBOT_INTRO + yml + ROBOT_FIN
    with io.open(os.path.join(OUT, "LEEME.txt"), "a", encoding="utf-8") as fh:
        fh.write(bloque)

    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print("Carpeta lista: %s" % OUT)
    for f in sorted(os.listdir(OUT)):
        print("  %-22s %8.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024.0))
    print("  %s  |  total %.0f KB" % (iconos, total / 1024.0))


if __name__ == "__main__":
    main()
