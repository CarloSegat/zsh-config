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

-- ── LSP ───────────────────────────────────────────────────────────
-- gd → LSP definition (overrides Vim's builtin local-file search)
map("n", "gd", vim.lsp.buf.definition, { desc = "LSP go to definition" })
map("n", "gD", vim.lsp.buf.declaration, { desc = "LSP go to declaration" })

-- ── Completion ────────────────────────────────────────────────────
-- CR accepts the native popup menu selection; otherwise inserts a normal newline
-- (This covers the built-in completion menu, not blink.cmp which has its own mappings)
-- ── Text formatting ───────────────────────────────────────────────
-- Wrap selected lines at sentence boundaries (avoids splitting e.g., i.e., etc.)
vim.api.nvim_create_user_command("WrapSentences", function(opts)
    local start_line = opts.line1
    local end_line   = opts.line2
    local lines  = vim.api.nvim_buf_get_lines(0, start_line - 1, end_line, false)
    local text   = table.concat(lines, " ")
    -- Protect abbreviations and ellipsis from splitting
    text = text:gsub("e%.g%.", "\1EG\1")
    text = text:gsub("i%.e%.", "\1IE\1")
    text = text:gsub("%.%.%.", "\1EL\1")
    -- Split at sentence-ending punctuation followed by space(s) and uppercase/digit
    local result = vim.fn.substitute(text, [[\([.!?]\)\s\+\([A-Z0-9]\)]], [[\1\n\2]], 'g')
    -- Restore protected tokens
    result = result:gsub("\1EG\1", "e.g.")
    result = result:gsub("\1IE\1", "i.e.")
    result = result:gsub("\1EL\1", "...")
    vim.api.nvim_buf_set_lines(0, start_line - 1, end_line, false, vim.split(result, "\n", { plain = true }))
end, { range = true })

map("x", "<leader>fw", ":WrapSentences<CR>", { desc = "Wrap at sentence boundaries" })

vim.keymap.set('v', '<leader>tb', [["zc\textbf{<C-r>z}<Esc>]], {
  desc = 'Wrap selection in \\textbf{}',
  noremap = true
})

map("i", "<CR>", function()
    if vim.fn.pumvisible() == 1 then
        -- Accept the selected completion item
        return "<C-y>"
    else
        -- Start a new undo block, then insert newline
        return "<C-g>u<CR>"
    end
end, { expr = true, desc = "Accept completion or newline" })
