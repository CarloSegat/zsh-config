-- keymaps.lua — All non-plugin-specific key mappings

local map = vim.keymap.set

-- ── Escape shortcuts ──────────────────────────────────────────────
-- jj exits insert mode (faster than reaching for Esc)
map("i", "jj", "<Esc>", { desc = "Exit insert mode" })

-- ── Command mode shortcut ─────────────────────────────────────────
-- Space Space opens the command line (like pressing :)
map("n", "<Space><Space>", ":", { desc = "Command mode" })

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
