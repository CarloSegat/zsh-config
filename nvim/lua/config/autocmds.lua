-- autocmds.lua — Autocommands

-- Reload buffer when the file is changed on disk by an external program.
-- autoread alone only fires on explicit commands; this triggers the actual check.
vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter", "CursorHold", "CursorHoldI" }, {
    group = vim.api.nvim_create_augroup("CheckExternalChanges", { clear = true }),
    pattern = "*",
    callback = function()
        if vim.fn.getcmdwintype() == "" then
            vim.cmd("checktime")
        end
    end,
    desc = "Auto-reload buffer when file changes on disk",
})

-- Sync named registers across Neovim instances via ShaDa.
-- On focus lost: write registers to ShaDa. On focus gained: read them back.
vim.api.nvim_create_autocmd("FocusLost", {
    group = vim.api.nvim_create_augroup("ShadaSync", { clear = true }),
    pattern = "*",
    command = "wshada",
    desc = "Write registers to ShaDa when leaving pane",
})
vim.api.nvim_create_autocmd("FocusGained", {
    group = "ShadaSync",
    pattern = "*",
    command = "rshada",
    desc = "Read registers from ShaDa when entering pane",
})

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
