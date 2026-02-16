-- indent-object.lua — Text objects based on indentation level
-- ii — select current indentation level (inner)
-- ai — select current indentation level + line above
-- aI — select current indentation level + line above and below
-- Use with any command expecting a motion: dii, vii, yai, etc.

return {
    "michaeljsmith/vim-indent-object",
    event = "BufReadPre", -- Load when opening a file
}
