-- lsp.lua — nvim-lspconfig + mason + mason-lspconfig
-- Mason installs LSP servers locally; mason-lspconfig bridges Mason ↔ lspconfig.

return {
    -- The LSP "engine": provides :LspInfo, :LspStart, etc.
    {
        "neovim/nvim-lspconfig",
        event = { "BufReadPre", "BufNewFile" }, -- Load when opening a file
        dependencies = {
            -- Mason: package manager that installs LSP servers into ~/.local/share/nvim/mason
            { "williamboman/mason.nvim" },
            -- Bridges Mason names ↔ lspconfig names and auto-installs servers
            { "williamboman/mason-lspconfig.nvim" },
        },
        config = function()
            -- 1. Setup Mason (must come first)
            require("mason").setup()

            -- 2. Setup Mason-LSPConfig with the servers you want auto-installed
            require("mason-lspconfig").setup({
                ensure_installed = {
                    "lua_ls",
                    "pyright",
                    "ts_ls",
                    "texlab",
                    "solidity_ls_nomicfoundation",
                },
            })

            -- 3. Custom per-server settings (vim.lsp.config is the new Neovim 0.11+ API)
            vim.lsp.config("pyright", {
                settings = {
                    python = { analysis = { autoSearchPaths = true } },
                },
            })

            -- 4. Enable all your LSP servers
            vim.lsp.enable({
                "pyright",
                "ts_ls",
                "lua_ls",
                "texlab",
                "solidity",
                "solidity_ls_nomicfoundation",
                "gdscript",
            })
        end,
    },
}
