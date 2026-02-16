-- blink-cmp.lua — Fast, Lua-native autocompletion engine

return {
    "Saghen/blink.cmp",
    event = "InsertEnter", -- Only load when you start typing
    -- blink.cmp uses pre-built binaries; this tells lazy.nvim which version to fetch
    version = "*",
    opts = {
        keymap = {
            -- Start with sensible defaults (Tab/S-Tab to navigate, etc.)
            preset = "default",
            -- Enter to accept the selected completion item
            ["<CR>"] = { "accept", "fallback" },
        },

        completion = {
            list = {
                selection = {
                    preselect = true,       -- Highlight the first item automatically
                    auto_insert = false,    -- Don't insert text until you confirm
                },
            },
        },
    },
}
