# DOTFILES

## gtk-2.0

GTK (GIMP Toolkit) is a library used by many GUI apps (Wireshark, Chromium, VS Code, etc.) to render windows, buttons, and menus.

The `gtk-2.0/gtkfilechooser.ini` file configures the **file picker dialog** — the window that appears when you click "Open File" or "Save As" in any GTK-based app.

## iterm2
Terminal emulator (Catppuccin Mocha, JetBrains Mono + Nerd Font)

## yazi
terminal file explorer

## claude
Global Claude Code config: `CLAUDE.md` (personal instructions), `settings.json`, `skills/`.
Symlinked into `~/.claude/` per-file — `~/.claude/` itself stays a real dir because it holds
hundreds of MB of session state.
