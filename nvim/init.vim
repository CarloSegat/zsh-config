" The MAPLEADER needs to be KEPT PRESSED to activate stuff
let mapleader = "," " map leader key as ,

" imap = valid in insert mode
" nmap = valid in normal mode
:imap jj <Esc>
:nmap <Space><Space> :

" ------- SPLITS ------
" editor
:nmap <leader>s :split<Cr>
:nmap <leader>vs :vsplit<Cr>
" Terminal
:nmap <leader>vt :vsplit term://zsh<Cr>
:nmap <leader>ht :split term://zsh<Cr>:tnoremap jj <C-\><C-n> " Exit Insert Mode


" :tnoremap <Esc><Esc> <C-\><C-N> "escape terminal mode.
" The problem is that in a terminal you cannot switch to a right-split editor
" unless you escape the insert mode needed in the terminal to input commands

" ------- MOVEMENT --------
" moving between windows disabled because using yazi for navigation
" :nmap <C-h> <C-w>h
" :nmap <C-j> <C-w>j
" :nmap <C-k> <C-w>k
" :nmap <C-l> <C-w>l
noremap H ^ " H to move to the first character in a line
noremap L g_" L to move to the last character in a line
:noremap J 5j " Move down file lines
:vnoremap J 5j " Move up file lines
:noremap K 5k
:vnoremap K 5k

" ------- NERDTREE --------
" close all buffers except nerdTree
" :noremap <leader>wa :%bd<Cr>:NERDTree<Cr>:wincmd p<Cr>
" :command E NERDTree " use NERDTree as default file explorer
" cancel NERDTree default mappings for J and K so that they work in NERDTree
" let NERDTreeMapJumpLastChild=''
" let NERDTreeMapJumpFirstChild=''
" open NERDTree when vim launches and moves cursor to file area
" autocmd VimEnter * NERDTree | wincmd p
" autocmd bufenter * if (winnr ("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif
" force nerdTRee ctrl+m popup to take one line, otherwise on
" mac it keeps occupying space after you closed it
" if has('mac')
"     let g:NERDTreeMinimalMenu=1
" endif

" ------- JSON -------
" use za to fold json
:set filetype=json
:syntax on
" :set foldmethod=syntax
:set foldmethod=indent

" ---------- Basics ---------
:filetype on " file type detection
set encoding=utf8
set autoindent " line below indented as line above
set smartindent
set shiftwidth=4 " default tab = 4 spaces
set smarttab
set clipboard=unnamedplus
set number " line numbers
set relativenumber
set incsearch " jump to search match as typing
set ignorecase " ignore case in searches
set smartcase  " use case in searches if u use CAPS
set noswapfile " if u don't disable this then vim would create .swp files automatically
autocmd BufWritePre * %s/\s\+$//e "Auto-remove trailing whitespace on save
set path+=** " so that /find becomes a fuzzy file finder
:set nofoldenable " so that when you open a file it doesnt start wrapped
" shows matches of a serach in a split
set inccommand=split
:set hlsearch "enable highligting
map <esc> :noh<cr> " hide highlights


" ----- Theme ----
" Display tabs and trailing spaces visually
set list listchars=tab:\ \ ,trail:·
syntax enable
highlight ColorColumn ctermbg=0 guibg=grey
" rulers, columns, lines at 79 and 100 characters
set colorcolumn=79,100


" ----- Spell Check ------
:set spell spelllang=en_us
:set spellsuggest=fast,20 "Don't show too much suggestion for spell check.
:set spellfile=~/.config/nvim/en.utf-8.add
" style for spell checking, has to be after configs that change theme/colors
hi clear SpellBad
" hi clear SpellCap
" hi clear SpellRare
hi clear SpellLocal
hi SpellBad cterm=underline ctermfg=red gui=undercurl guisp=red
hi SpellLocal cterm=underline ctermfg=blue gui=undercurl guisp=blue

" git-fugitive highlights
hi DiffRemoved ctermfg=red
hi DiffAdded ctermfg=green
let g:fugitive_dynamic_colors = 1

" ------ Snippets ------
" Pastes a print statement with the yanked variable inside {} making sure to
" keep indentation as above
nnoremap <leader>pp :read ~/.config/nvim/snippets/python/printf.py<Cr>t{pt}pk0y^jP
nnoremap <leader>tsi :read ~/.config/nvim/snippets/typescript/print.ts<Cr>t$pt}p

" ------ Plugins ------
call plug#begin('~/.config/nvim/bundle') " where plugins are stored

set nowritebackup
set updatetime=100

" The 'Engine' (Native LSP configs)
Plug 'neovim/nvim-lspconfig'

" autocompletion
Plug 'Saghen/blink.cmp'

" The 'Mechanic' (Package manager for LSPs)
Plug 'williamboman/mason.nvim'
Plug 'williamboman/mason-lspconfig.nvim'

" the return key can be used to say yes to autoimport suggestion if you see it
" "\<C-y> Inserts the Ctrl-Y keystroke
" \<C-g>u: Starts a new undo sequence (undo breakpoint). if you later press u (undo),
" it will only undo from this point onward,
inoremap <expr> <cr> pumvisible() ? "\<C-y>" : "\<C-g>u\<CR>"

" ----- VIM INDENT OBJECT
" <command expecting motion>ai (includes line above=
" <command expecting motion>ii (only current indentation level and nested)
" you can keep pressing ii to EXTEND the selection to outer indentation levels
Plug 'michaeljsmith/vim-indent-object'

" ----- VIM SURROUND -----
" change surroundings cs
"   cs"'
"   cst" (o change a tag)
" add surroundings ys
"   yss<tag or symbol> will surround the text on the line
"   ysiw" surrounds inside word
" delete surroundings ds
" VS<tag or symbol> surrounds a visual block
Plug 'tpope/vim-surround'

Plug 'tpope/vim-fugitive'

" for minus and plus signs if you open a changed file
Plug 'lewis6991/gitsigns.nvim'

" fzf is a fuzzy file finder
" it can find files by name or content
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'

" svelte syntax hoghlighter
Plug 'othree/html5.vim'
Plug 'pangloss/vim-javascript'
Plug 'evanleck/vim-svelte', {'branch': 'main'}

call plug#end()

" fzf to search file name
nnoremap <C-p> :Files<Cr>
" fzf to search file content
nnoremap <C-k>k :Ag<Cr>
" below fixes Ag failing
let $FZF_DEFAULT_COMMAND=""

lua << EOF
-- 1. Setup Mason
require("mason").setup()

require('blink.cmp').setup({
  keymap = {
    -- We'll start with the 'default' preset and then add our overrides
    preset = 'default',

    ['<CR>'] = { 'accept', 'fallback' }, -- Enter to accept
  },

  -- Recommended: Disable "auto_insert" so J/K don't accidentally
  -- type into the buffer while you are scrolling the list
  completion = {
    list = { selection = { preselect = true, auto_insert = false } }
  }
})

-- 2. Setup Mason-LSPConfig
require("mason-lspconfig").setup({
    -- Put the LSPs you want here
    ensure_installed = {
	"lua_ls",
	"pyright",
	"ts_ls",
	"texlab",
	"solidity_ls_nomicfoundation",
    }
})

-- Define custom settings/overrides
vim.lsp.config('pyright', {
    settings = {
        python = { analysis = { autoSearchPaths = true } }
    }
})

-- Enable the servers
vim.lsp.enable({
    'pyright',
    'ts_ls',
    'lua_ls',
    'texlab',
    'solidity',
    'solidity_ls_nomicfoundation',
    'gdscript'
})
EOF
