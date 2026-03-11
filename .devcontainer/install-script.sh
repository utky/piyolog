curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org -o /tmp/ghcup
chmod +x /tmp/ghcup
BOOTSTRAP_HASKELL_NONINTERACTIVE=1 /tmp/ghcup --cache

echo "source /home/vscode/.ghcup/env" >> ~/.bashrc

curl -fsSL https://claude.ai/install.sh | bash
