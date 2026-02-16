-- gitsigns.lua — Git change indicators in the sign column (+, -, ~)

return {
    "lewis6991/gitsigns.nvim",
    event = "BufReadPre", -- Load when opening a file (needs to diff against git)
    opts = {},            -- Empty opts calls setup() with defaults
}
