#!/usr/bin/env bash
# Construye el repositorio apt firmado de OweeCapture (para publicarlo en GitHub Pages): quien lo tiene configurado actualiza con `sudo apt update && sudo apt upgrade`.
# Uso: packaging/crear_repo_apt.sh <archivo.deb> <carpeta-de-salida>        (la clave de firma debe estar en el llavero de gpg; con APT_GPG_KEY_ID se elige una concreta)
# Solo se publica la última versión: apt solo necesita esa. La clave pública va en `oweecapture.gpg`, en la raíz del sitio.
set -euo pipefail
DEB="${1:?falta el .deb}"; SALIDA="${2:?falta la carpeta de salida}"; RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${APT_GPG_KEY_ID:-$(gpg --list-secret-keys --with-colons | awk -F: '/^sec/ {print $5; exit}')}"; [ -n "$KEY" ] || { echo "no hay clave secreta de gpg para firmar" >&2; exit 1; }
rm -rf "$SALIDA"; mkdir -p "$SALIDA/pool/main" "$SALIDA/dists/stable/main/binary-all"; cp "$DEB" "$SALIDA/pool/main/"; cd "$SALIDA"
apt-ftparchive packages pool > dists/stable/main/binary-all/Packages; gzip -9 -k -n dists/stable/main/binary-all/Packages
apt-ftparchive -o APT::FTPArchive::Release::Origin=OweeCapture -o APT::FTPArchive::Release::Label=OweeCapture -o APT::FTPArchive::Release::Suite=stable -o APT::FTPArchive::Release::Codename=stable \
  -o APT::FTPArchive::Release::Architectures=all -o APT::FTPArchive::Release::Components=main release dists/stable > dists/stable/Release
gpg --batch --yes --pinentry-mode loopback --passphrase "${APT_GPG_PASSPHRASE:-}" -u "$KEY" --detach-sign --armor -o dists/stable/Release.gpg dists/stable/Release
gpg --batch --yes --pinentry-mode loopback --passphrase "${APT_GPG_PASSPHRASE:-}" -u "$KEY" --clearsign -o dists/stable/InRelease dists/stable/Release
gpg --export "$KEY" > oweecapture.gpg; touch .nojekyll          # .nojekyll: GitHub Pages sirve los archivos tal cual
cat > index.html <<'HTML'
<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OweeCapture - repositorio apt</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}pre{background:#102019;color:#eff0f1;padding:1rem;border-radius:8px;overflow:auto}</style>
<h1>OweeCapture - repositorio apt</h1>
<p>Para Debian, Ubuntu, Deepin, Mint y derivadas. Con el repositorio configurado, las versiones nuevas llegan con <code>sudo apt update &amp;&amp; sudo apt upgrade</code>.</p>
<pre>sudo install -d /usr/share/keyrings
curl -fsSL https://oweeme.github.io/oweecapture/oweecapture.gpg | sudo tee /usr/share/keyrings/oweecapture-archive-keyring.gpg &gt;/dev/null
echo "deb [signed-by=/usr/share/keyrings/oweecapture-archive-keyring.gpg] https://oweeme.github.io/oweecapture stable main" | sudo tee /etc/apt/sources.list.d/oweecapture.list
sudo apt update &amp;&amp; sudo apt install oweecapture</pre>
<p>Si instalaste el <code>.deb</code> de la <a href="https://github.com/oweeme/oweecapture/releases/latest">última versión</a>, el repositorio ya queda configurado.</p>
<p>English: add the repository above, then <code>sudo apt update &amp;&amp; sudo apt upgrade</code> installs new versions. The <code>.deb</code> from the latest release configures it for you.</p>
HTML
echo "repositorio apt en $SALIDA (clave $KEY)"
