-- fzf.lua — Fuzzy finder for files (by name) and file content (grep)

return {
    {
        "junegunn/fzf",
        build = function() vim.fn["fzf#install"]() end, -- Run the fzf installer on update
    },
    {
        "junegunn/fzf.vim",
        dependencies = { "junegunn/fzf" },
        -- Only load when you press Ctrl-P (files) or Ctrl-S (grep)
        keys = {
            { "<C-p>", function()
                local root = vim.fn.systemlist('git rev-parse --show-toplevel 2>/dev/null')[1]
                if vim.v.shell_error ~= 0 then root = vim.fn.getcwd() end
                vim.fn['fzf#vim#files'](root, vim.fn['fzf#vim#with_preview'](), 0)
            end, desc = "FZF: find files by name (git root)" },
            { "<C-s>", ":Rg<CR>", desc = "FZF: search file contents (rg)" },
        },
        config = function()
            -- Ensure preview highlights match the actual search results
            vim.g.fzf_preview_window = { 'right:50%', 'ctrl-/' }

            local function git_root()
                local root = vim.fn.systemlist('git rev-parse --show-toplevel 2>/dev/null')[1]
                if vim.v.shell_error ~= 0 then return vim.fn.getcwd() end
                return root
            end

            -- Use exact matching for Rg to avoid highlight mismatches (disable fuzzy matching)
            -- Search from git root so results aren't scoped to the current directory
            vim.api.nvim_create_user_command('Rg', function(opts)
                local dir = git_root()
                vim.fn['fzf#vim#grep'](
                    'rg --column --line-number --no-heading --with-filename --color=always --smart-case -- ' ..
                    vim.fn.shellescape(opts.args),
                    vim.fn['fzf#vim#with_preview']({ dir = dir, options = '--exact --delimiter : --nth 4.. --no-hscroll' }),
                    0
                )
            end, { nargs = '*' })
        end,
    },
}
