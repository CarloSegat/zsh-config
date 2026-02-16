-- autocmds.lua — Autocommands

-- Strip trailing whitespace on every save.
-- Preserves cursor position so you don't jump around after :w.
vim.api.nvim_create_autocmd("BufWritePre", {
    pattern = "*",
    callback = function()
        -- Save cursor position
        local pos = vim.api.nvim_win_get_cursor(0)
        -- Remove trailing whitespace (silent so it doesn't error on no match)
        vim.cmd([[%s/\s\+$//e]])
        -- Restore cursor position (clamp row in case the file got shorter)
        local last_line = vim.api.nvim_buf_line_count(0)
        pos[1] = math.min(pos[1], last_line)
        vim.api.nvim_win_set_cursor(0, pos)
    end,
    desc = "Auto-remove trailing whitespace on save",
})
