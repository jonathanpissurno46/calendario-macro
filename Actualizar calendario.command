#!/bin/bash
# ============================================================
#  ACTUALIZAR EL CALENDARIO WEB
#  Doble clic sobre este archivo cuando cambies el calendario.
#
#  Hace dos cosas:
#    1. Regenera la carpeta "calendario-web" desde el archivo maestro.
#    2. Abre esa carpeta en el Finder para que arrastres los archivos
#       nuevos a GitHub.
# ============================================================

cd "$(dirname "$0")" || exit 1

echo ""
echo "=============================================="
echo "  ACTUALIZANDO EL CALENDARIO WEB"
echo "=============================================="
echo ""

# Elige un Python que tenga Pillow (para los iconos); si no, usa el del sistema.
PY=""
for CANDIDATO in \
  "/Users/jonathanpissurno/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3" \
  "$(command -v python3)"; do
  if [ -x "$CANDIDATO" ] && "$CANDIDATO" -c "import PIL" >/dev/null 2>&1; then
    PY="$CANDIDATO"; break
  fi
done
[ -z "$PY" ] && PY="$(command -v python3)"

echo "Usando: $PY"
echo ""

"$PY" build-web.py || { echo ""; echo "ERROR: no se pudo regenerar. Avisa a tu asistente."; read -r -p "Pulsa Enter para cerrar..."; exit 1; }

echo ""
echo "=============================================="
echo "  AHORA SUBE EL ARCHIVO A GITHUB"
echo "=============================================="
echo ""
echo "  Se acaba de abrir la carpeta 'calendario-web'."
echo ""
echo "  OPCION RAPIDA (recomendada):"
echo "   1. Entra en tu repositorio en GitHub."
echo "   2. Pulsa 'Add file'  >  'Upload files'."
echo "   3. Arrastra el archivo  index.html  desde la carpeta abierta."
echo "   4. Pulsa 'Commit changes'."
echo "   5. Espera 1 minuto y recarga la web (Cmd + Shift + R)."
echo ""
echo "  OPCION COMPLETA (si cambiaste iconos, textos de la app, etc.):"
echo "   Arrastra TODOS los archivos de la carpeta, no solo index.html."
echo ""
echo "  SOLO hay que subir si cambias el CALENDARIO o la APP."
echo "  Tus eventos propios, datos reales y filtros NO se suben:"
echo "  viven en el navegador de cada dispositivo."
echo ""

open "calendario-web" 2>/dev/null

read -r -p "Pulsa Enter para cerrar esta ventana..."
