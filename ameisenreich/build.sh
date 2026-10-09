#!/bin/sh
# Wraps the artifact fragment into a standalone page (index.html) for local play / hosting.
cd "$(dirname "$0")"
{ printf '<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n<meta name="apple-mobile-web-app-capable" content="yes">\n</head>\n<body>\n'; cat game.html; printf '\n</body>\n</html>\n'; } > index.html
