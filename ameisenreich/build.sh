#!/bin/sh
# Builds the standalone web app (index.html) and the Capacitor web bundle (www/) from game.html.
# game.html is the single source; it is also what gets published as the claude.ai artifact.
set -e
cd "$(dirname "$0")"
{
  printf '<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">\n'
  printf '<meta name="theme-color" content="#120d09">\n'
  printf '<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="mobile-web-app-capable" content="yes">\n'
  printf '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
  printf '<meta name="apple-mobile-web-app-title" content="Ameisenreich">\n'
  printf '<link rel="manifest" href="manifest.webmanifest">\n<link rel="apple-touch-icon" href="assets/icon-180.png">\n'
  printf '<link rel="icon" type="image/png" href="assets/icon-192.png">\n'
  printf '<style>:root{padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) 0 env(safe-area-inset-left,0px);box-sizing:border-box;height:100%%}</style>\n'
  printf '</head>\n<body>\n'
  cat game.html
  printf '\n<script>if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost") && location.protocol !== "capacitor:") navigator.serviceWorker.register("sw.js").catch(function(){});</script>\n'
  printf '</body>\n</html>\n'
} > index.html
rm -rf www && mkdir -p www/assets
cp index.html manifest.webmanifest sw.js www/
cp assets/icon-180.png assets/icon-192.png assets/icon-512.png www/assets/
echo "Built index.html and www/"
