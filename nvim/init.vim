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
hi SpellBad cterm=underline ctermfg=red

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

Plug 'neoclide/coc.nvim', {'branch': 'release'}
set nowritebackup
set updatetime=100
" Use tab for trigger completion
" NOTE: Use command ':verbose imap <tab>' to make sure tab is not mapped by
" other plugin before putting this into your config.
" inoremap = insermode, no recursive remapping
" <silent> = Suppresses any output or echoing to the command line when the mapping is triggered.
" <expr> = Treats RHS of mapping as expression to evaluate dynamically, rather literal
" coc#pum#visible() is a function call in vimscript. It calls the visible
" function in the coc#pum namespace (pum=pop-up menu). It checks if the pop-up
" is open
" the \<Tab> escapes the <Tab> so that it's interpreted as a character and not
" as a command
inoremap <silent><expr> <TAB> coc#pum#visible() ? coc#pum#next(1) : "\<Tab>"
inoremap <expr><S-TAB> coc#pum#visible() ? coc#pum#prev(1) : "\<C-h>"
" GoTo code navigation.
nmap <silent> gd <Plug>(coc-definition)
nmap <silent> gy <Plug>(coc-type-definition)
nmap <silent> gi <Plug>(coc-implementation)
nmap <silent> gr <Plug>(coc-references)
nnoremap <leader>rn <Plug>(coc-rename)

" the return key can be used to say yes to autoimport suggestion if you see it
" "\<C-y> Inserts the Ctrl-Y keystroke
" \<C-g>u: Starts a new undo sequence (undo breakpoint). if you later press u (undo),
" it will only undo from this point onward,
inoremap <expr> <cr> pumvisible() ? "\<C-y>" : "\<C-g>u\<CR>"

" ------ LANGUAGE SERVERS ------
" Python
Plug 'fannheyward/coc-pyright', {'do': 'yarn install --frozen-lockfile'}
" typscript
Plug 'neoclide/coc-tsserver', {'do': 'yarn install --frozen-lockfile'}

" ----- VIM INDENT OBJECT
" <command expecting motion>ai (includes line above=
" <command expecting motion>ii (only current indentation level and nested)
" you can keep pressing ii to EXTEND the selection to outer indentation levels
Plug 'michaeljsmith/vim-indent-object'

" ----- NERD TREE -----
" Plug 'scrooloose/nerdtree'

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
