-- keymaps.lua — All non-plugin-specific key mappings

local map = vim.keymap.set

-- ── Escape shortcuts ──────────────────────────────────────────────
-- jj exits insert mode (faster than reaching for Esc)
map("i", "jj", "<Esc>", { desc = "Exit insert mode" })
-- jj also exits terminal mode (works for all terminal entry methods)
map("t", "jj", [[<C-\><C-n>]], { desc = "Exit terminal mode" })

-- ── Command mode shortcut ─────────────────────────────────────────
-- Space Space opens the command line (like pressing :)
map("n", "<Space><Space>", ":", { desc = "Command mode" })

-- ── Splits ────────────────────────────────────────────────────────
map("n", "<leader>s", ":split<CR>", { desc = "Horizontal split" })
map("n", "<leader>vs", ":vsplit<CR>", { desc = "Vertical split" })
map("n", "<leader>vt", ":vsplit term://zsh<CR>", { desc = "Vertical terminal split" })
map("n", "<leader>ht", ":split term://zsh<CR>", { desc = "Horizontal terminal split" })

-- ── Movement ──────────────────────────────────────────────────────
-- H/L jump to first/last non-blank character on the line
-- Applied to normal, visual, and operator-pending modes
map({ "n", "v", "o" }, "H", "^", { desc = "First non-blank char" })
map({ "n", "v", "o" }, "L", "g_", { desc = "Last non-blank char" })

-- J/K move 5 lines at a time for faster vertical navigation
map({ "n", "v", "o" }, "J", "5j", { desc = "Move 5 lines down" })
map({ "n", "v", "o" }, "K", "5k", { desc = "Move 5 lines up" })

-- ── Search ────────────────────────────────────────────────────────
-- Esc clears search highlights
map("n", "<Esc>", ":noh<CR>", { desc = "Clear search highlights" })

-- ── Completion ────────────────────────────────────────────────────
-- CR accepts the native popup menu selection; otherwise inserts a normal newline
-- (This covers the built-in completion menu, not blink.cmp which has its own mappings)
map("i", "<CR>", function()
    if vim.fn.pumvisible() == 1 then
        -- Accept the selected completion item
        return "<C-y>"
    else
        -- Start a new undo block, then insert newline
        return "<C-g>u<CR>"
    end
end, { expr = true, desc = "Accept completion or newline" })

-- ── Snippets ──────────────────────────────────────────────────────
-- ,pp  — Insert a Python print() with the yanked variable
map("n", "<leader>pp",
    ":read ~/.config/nvim/snippets/python/printf.py<CR>t{pt}pk0y^jP",
    { desc = "Python print snippet" })

-- ,tsi — Insert a TypeScript console.log with the yanked variable
map("n", "<leader>tsi",
    ":read ~/.config/nvim/snippets/typescript/print.ts<CR>t$pt}p",
    { desc = "TS console.log snippet" })
