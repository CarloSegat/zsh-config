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
            { "<C-k>k", ":Ag<CR>", desc = "FZF: search file contents (ag)" },
        },
    },
}
