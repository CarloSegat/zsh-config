-- surround.lua — Manipulate surrounding characters (quotes, brackets, tags)
-- cs"'  — change surrounding " to '
-- ds"   — delete surrounding "
-- ysiw" — surround inner word with "
-- VS<p> — surround visual selection with <p> tag

return {
    "tpope/vim-surround",
    event = "BufReadPre", -- Load when opening a file
}
