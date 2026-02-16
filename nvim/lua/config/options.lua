-- options.lua — All vim.opt / vim.g settings (translated from set commands)

-- Encoding
vim.opt.encoding = "utf8"

-- Indentation
vim.opt.autoindent = true    -- New line inherits indentation from the line above
vim.opt.smartindent = true   -- Auto-indent after {, keywords, etc.
vim.opt.shiftwidth = 4       -- Default indent = 4 spaces
vim.opt.smarttab = true      -- Tab respects shiftwidth at the beginning of a line

-- Clipboard — use system clipboard for yank/paste
vim.opt.clipboard = "unnamedplus"

-- Line numbers
vim.opt.number = true         -- Show absolute line number on current line
vim.opt.relativenumber = true -- Show relative numbers on other lines

-- Search
vim.opt.incsearch = true   -- Jump to match as you type the search pattern
vim.opt.ignorecase = true  -- Case-insensitive search by default
vim.opt.smartcase = true   -- …unless the query contains uppercase letters
vim.opt.hlsearch = true    -- Highlight all search matches

-- File handling
vim.opt.swapfile = false      -- Don't create .swp files
vim.opt.writebackup = false   -- Don't create backup before overwriting

-- Folding — open files unfolded
vim.opt.foldenable = false
vim.opt.foldmethod = "indent"

-- Live substitution preview in a split (neovim-specific)
vim.opt.inccommand = "split"

-- Faster CursorHold events (used by gitsigns, LSP, etc.)
vim.opt.updatetime = 100

-- Fuzzy file finding with :find
vim.opt.path:append("**")

-- Visible whitespace — show tabs and trailing spaces
vim.opt.list = true
vim.opt.listchars = { tab = "  ", trail = "·" }

-- Rulers at 79 and 100 characters
vim.opt.colorcolumn = "79,100"

-- Spell checking
vim.opt.spell = true
vim.opt.spelllang = "en_us"
vim.opt.spellsuggest = "fast,20"                       -- Limit suggestions for speed
vim.opt.spellfile = vim.fn.expand("~/.config/nvim/en.utf-8.add")

-- Syntax highlighting (vim.cmd because there's no pure-Lua equivalent)
vim.cmd("syntax enable")
vim.cmd("filetype on")

-- ---------- Highlight overrides ----------
-- Must come after syntax/colorscheme so they aren't overwritten

-- Spell highlights: underline instead of background color
vim.cmd("hi clear SpellBad")
vim.cmd("hi clear SpellLocal")
vim.cmd("hi SpellBad cterm=underline ctermfg=red gui=undercurl guisp=red")
vim.cmd("hi SpellLocal cterm=underline ctermfg=blue gui=undercurl guisp=blue")

-- Git-fugitive diff colors
vim.cmd("hi DiffRemoved ctermfg=red")
vim.cmd("hi DiffAdded ctermfg=green")

-- Ruler column color
vim.cmd("highlight ColorColumn ctermbg=0 guibg=grey")

-- ---------- Plugin globals ----------
vim.g.fugitive_dynamic_colors = 1

-- fzf: empty default command so :Ag doesn't fail
vim.env.FZF_DEFAULT_COMMAND = ""
