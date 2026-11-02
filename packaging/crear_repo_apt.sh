#!/usr/bin/env bash
# Construye el repositorio apt firmado de OweeCapture (para publicarlo en GitHub Pages): quien lo tiene configurado actualiza con `sudo apt update && sudo apt upgrade`.
# Uso: packaging/crear_repo_apt.sh <archivo.deb> <carpeta-de-salida>        (la clave de firma debe estar en el llavero de gpg; con APT_GPG_KEY_ID se elige una concreta)
# Solo se publica la última versión: apt solo necesita esa. La clave pública va en `oweecapture.gpg`, en la raíz del sitio, junto a la página del proyecto (web/).
set -euo pipefail
DEB="$(realpath "${1:?falta el .deb}")"; SALIDA="${2:?falta la carpeta de salida}"; RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${APT_GPG_KEY_ID:-$(gpg --list-secret-keys --with-colons | awk -F: '/^sec/ {print $5; exit}')}"; [ -n "$KEY" ] || { echo "no hay clave secreta de gpg para firmar" >&2; exit 1; }
rm -rf "$SALIDA"; mkdir -p "$SALIDA/pool/main" "$SALIDA/dists/stable/main/binary-all"; cp "$DEB" "$SALIDA/pool/main/"; cd "$SALIDA"
apt-ftparchive packages pool > dists/stable/main/binary-all/Packages; gzip -9 -k -n dists/stable/main/binary-all/Packages
apt-ftparchive -o APT::FTPArchive::Release::Origin=OweeCapture -o APT::FTPArchive::Release::Label=OweeCapture -o APT::FTPArchive::Release::Suite=stable -o APT::FTPArchive::Release::Codename=stable \
  -o APT::FTPArchive::Release::Architectures=all -o APT::FTPArchive::Release::Components=main release dists/stable > dists/stable/Release
gpg --batch --yes --pinentry-mode loopback --passphrase "${APT_GPG_PASSPHRASE:-}" -u "$KEY" --detach-sign --armor -o dists/stable/Release.gpg dists/stable/Release
gpg --batch --yes --pinentry-mode loopback --passphrase "${APT_GPG_PASSPHRASE:-}" -u "$KEY" --clearsign -o dists/stable/InRelease dists/stable/Release
gpg --export "$KEY" > oweecapture.gpg; touch .nojekyll          # .nojekyll: GitHub Pages sirve los archivos tal cual
# la página del proyecto (web/): se copia entera y se rellenan la versión y la suma SHA-256 del .deb
VERSION="$(dpkg-deb -f "$DEB" Version)"; SUMA="$(sha256sum "$DEB" | cut -d' ' -f1)"
cp -r "$RAIZ/web/." .; sed -i -e "s/@VERSION@/$VERSION/g" -e "s/@SHA256@/$SUMA/g" index.html
echo "repositorio apt en $SALIDA (clave $KEY)"
