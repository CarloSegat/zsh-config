-- LaTeX file type settings for better navigation with gf

-- Add .tex extension when using gf (go to file)
vim.opt_local.suffixesadd = '.tex'

-- Set up include pattern to recognize \input and \include commands
vim.opt_local.include = [[\\\%(input\|include\)\s*{]]

-- Configure includeexpr to handle LaTeX paths intelligently
-- This strips 'mystuff/' prefix if present (since we're already in mystuff/)
-- and normalizes path separators
vim.opt_local.includeexpr = [[substitute(substitute(v:fname, '^mystuff/', '', ''), '\\', '/', 'g')]]

-- Add search paths for gf navigation
-- '.' = current directory
-- '..' = parent directory
-- '**' = recursive search in subdirectories
vim.opt_local.path:append('.,..,..,mystuff/**,**')

-- Set iskeyword to include path characters for better word recognition
vim.opt_local.iskeyword:append('/')
vim.opt_local.iskeyword:append('-')

-- Optional: Show message when ftplugin loads
-- vim.notify("LaTeX ftplugin loaded - gf navigation enabled", vim.log.levels.INFO)

-- ========== Beamer Frame Folding ==========
vim.opt_local.foldmethod = "marker"
vim.opt_local.foldmarker = "\\begin{frame},\\end{frame}"
vim.opt_local.foldenable = true
