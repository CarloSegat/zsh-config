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
                    "ltex",
                    "gopls",
                },
            })

            -- 3. Custom per-server settings (vim.lsp.config is the new Neovim 0.11+ API)
            vim.lsp.config("pyright", {
                settings = {
                    python = { analysis = { autoSearchPaths = true } },
                },
            })

            vim.lsp.config("solidity_ls_nomicfoundation", {
                cmd = { "nomicfoundation-solidity-language-server", "--stdio" },
                filetypes = { "solidity" },
                root_markers = { "foundry.toml", "hardhat.config.js", "hardhat.config.ts", "remappings.txt", ".git" },
                single_file_support = true,
            })

            vim.lsp.config("ltex", {
                filetypes = { "markdown", "tex", "text", "gitcommit" },
                settings = {
                    ltex = {
                        language = "en-US",
                        additionalRules = {
                            enablePickyRules = false, -- Disable strict checking for technical writing
                            motherTongue = "en-US",
                        },
                        -- Add Italian and German for multilingual support
                        -- To switch language: :lua vim.lsp.buf.execute_command({command = "_ltex.changeLanguage", arguments = {"de"}})
                        enabled = { "en-US", "it", "de" },
                    },
                },
            })

            -- 4. Enable all your LSP servers
            vim.lsp.enable({
                "pyright",
                "ts_ls",
                "lua_ls",
                "texlab",
                "solidity_ls_nomicfoundation",
                "gdscript",
                "ltex",
                "gopls",
            })
        end,
    },
}
