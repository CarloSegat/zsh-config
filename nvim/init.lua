-- init.lua — Entry point: bootstrap lazy.nvim, set leader, load config modules

-- Set leader key BEFORE lazy.nvim setup (lazy.nvim uses it for key mappings)
vim.g.mapleader = ","

-- ── Bootstrap lazy.nvim ───────────────────────────────────────────
-- Auto-installs lazy.nvim into ~/.local/share/nvim/lazy/ on first launch
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
    vim.fn.system({
        "git", "clone", "--filter=blob:none",
        "https://github.com/folke/lazy.nvim.git",
        "--branch=stable",
        lazypath,
    })
end
vim.opt.rtp:prepend(lazypath)

-- ── Load config modules ──────────────────────────────────────────
require("config.options")  -- vim.opt settings, highlights, globals
require("config.keymaps")  -- non-plugin keymaps
require("config.autocmds") -- autocommands (trailing whitespace strip)

-- ── Setup lazy.nvim ──────────────────────────────────────────────
-- Loads every file in lua/plugins/ as a plugin spec
require("lazy").setup("plugins")
