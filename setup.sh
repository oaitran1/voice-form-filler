#!/usr/bin/env bash
# One-time setup on Mac or Linux:  ./setup.sh      (Windows: setup.ps1)
# Installs the tools, downloads the two AI models (~10 GB, once), installs the app and checks it works.
# Safe to run again: anything already done is skipped. Your data/profile.yaml is never overwritten.
set -euo pipefail
cd "$(dirname "$0")"

AI_MODEL="gemma3:12b"  # same as DEFAULT_MODEL in src/vff/extract.py
OLLAMA_URL="http://localhost:11434/api/version"

have() { command -v "$1" >/dev/null 2>&1; }
step() { printf '\n==> %s\n' "$1"; }

install_mac_tools() {
  if ! have brew; then
    step "Installing Homebrew (asks for your Mac password)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  fi
  for tool in uv ffmpeg ollama; do
    have "$tool" || { step "Installing $tool"; brew install "$tool"; }
  done
  brew services start ollama >/dev/null 2>&1 || true
}

install_linux_tools() {
  if ! have uv; then
    step "Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  if ! have ollama; then
    step "Installing Ollama (asks for your password)"
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  if ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
    step "Installing the microphone library (PortAudio, asks for your password)"
    if have apt-get; then sudo apt-get install -y libportaudio2
    elif have dnf; then sudo dnf install -y portaudio
    elif have pacman; then sudo pacman -S --noconfirm portaudio
    else echo "Please install PortAudio with your package manager, then run ./setup.sh again." >&2; exit 1
    fi
  fi
}

case "$(uname -s)" in
  Darwin) install_mac_tools ;;
  Linux) install_linux_tools ;;
  *) echo "On Windows, run setup.ps1 instead (see README)." >&2; exit 1 ;;
esac

step "Starting the local AI"
if ! curl -fsS "$OLLAMA_URL" >/dev/null 2>&1; then
  (nohup ollama serve >/dev/null 2>&1 &)
  for _ in $(seq 20); do curl -fsS "$OLLAMA_URL" >/dev/null 2>&1 && break; sleep 1; done
fi
curl -fsS "$OLLAMA_URL" >/dev/null || { echo "The local AI (Ollama) did not start. Try: ollama serve" >&2; exit 1; }

if ! ollama list | grep -q "^$AI_MODEL "; then
  step "Downloading the local AI ($AI_MODEL, about 8 GB, once)"
  ollama pull "$AI_MODEL"
fi

step "Installing the app"
uv sync

step "Downloading the speech-to-text model (about 1.5 GB, once)"
uv run make-report --setup

made_profile=no
if [ ! -f data/profile.yaml ]; then
  mkdir -p data
  cp templates/examples/company_profile.yaml data/profile.yaml
  made_profile=yes
fi

step "Checking it works (the 3 test stories, typed — no microphone; a few minutes)"
uv run live-test --typed --no-open </dev/null

printf '\n✓ Set up.\n'
if [ "$made_profile" = yes ]; then
  echo "  Next: open data/profile.yaml and type your company's details (it holds a sample company now)."
fi
echo "  Then: uv run record   (press Enter, tell what happened, say \"stop recording\")"
