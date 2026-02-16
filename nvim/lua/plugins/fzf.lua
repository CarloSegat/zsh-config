-- fzf.lua — Fuzzy finder for files (by name) and file content (grep)

return {
    {
        "junegunn/fzf",
        build = function() vim.fn["fzf#install"]() end, -- Run the fzf installer on update
    },
    {
        "junegunn/fzf.vim",
        dependencies = { "junegunn/fzf" },
        -- Only load when you press Ctrl-P (files) or Ctrl-K K (grep)
        keys = {
            { "<C-p>", ":Files<CR>", desc = "FZF: find files by name" },
            { "<C-s>", ":Rg<CR>", desc = "FZF: search file contents (rg)" },
        },
        config = function()
            -- Ensure preview highlights match the actual search results
            vim.g.fzf_preview_window = { 'right:50%', 'ctrl-/' }
            -- Use exact matching for Rg to avoid highlight mismatches (disable fuzzy matching)
            vim.api.nvim_create_user_command('Rg', function(opts)
                vim.fn['fzf#vim#grep'](
                    'rg --column --line-number --no-heading --color=always --smart-case -- ' .. vim.fn.shellescape(opts.args),
                    1,
                    vim.fn['fzf#vim#with_preview']({ options = '--exact --delimiter : --nth 3..' }),
                    0
                )
            end, { nargs = '*' })
        end,
    },
}
