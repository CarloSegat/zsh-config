-- fugitive.lua — Git wrapper (:Git blame, :Git diff, :Gvdiffsplit, etc.)

return {
    "tpope/vim-fugitive",
    -- Only load when you run a fugitive command (keeps startup fast)
    cmd = { "Git", "G", "Gvdiffsplit", "Gdiffsplit", "Gread", "Gwrite", "GBrowse" },
}
