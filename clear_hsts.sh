#!/bin/bash
echo "Limpiando HSTS de Chrome/Chromium..."

# Cierra navegadores
killall chrome 2>/dev/null
killall chromium 2>/dev/null
killall brave-browser 2>/dev/null

# Encuentra y limpia archivos HSTS
CHROME_PROFILES=(
    "$HOME/.config/google-chrome/Default"
    "$HOME/.config/chromium/Default"
    "$HOME/.config/BraveSoftware/Brave-Browser/Default"
)

for profile in "${CHROME_PROFILES[@]}"; do
    if [ -f "$profile/TransportSecurity" ]; then
        echo "Limpiando: $profile/TransportSecurity"
        rm -f "$profile/TransportSecurity"
        rm -f "$profile/TransportSecurity~"
    fi
done

echo "✅ HSTS limpiado. Abre el navegador de nuevo."
