# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"
# source ~/.bash_profile

# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="powerlevel10k/powerlevel10k"

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
plugins=(git)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"


# Load version control information
autoload -Uz vcs_info
precmd() { vcs_info }
# Format the vcs_info_msg_0_ variable
zstyle ':vcs_info:git:*' formats 'B:%b'


# Allow substitutions and expansions in the prompt
setopt prompt_subst

export PLAYDATE_SDK_PATH="/Users/carlosegat/Developer/PlaydateSDK"
export PATH=$PATH:$PLAYDATE_SDK_PATH/bin

export PATH="$PATH:/usr/local/share/dotnet/dotnet"

# Linux specific configuration
if [[ `uname` == "Darwin" ]]; then
    export PATH=$PATH:/opt/homebrew/bin
elif [[ `uname` == "Linux" ]]; then
    export PATH=$PATH:"/opt/Postman/"
    export PATH="$PATH:/opt/blender/"
    xmodmap ~/.Xmodmap
else
    echo "OS unrecognised"
fi

alias n="nvim"
alias r="reset"
alias python='python3'

# add folder .zfunc to list of folders that zsh is aware of to load functions from
fpath=( ~/.zfunc "${fpath[@]}" )
autoload -Uz git_add_commit_push
autoload -Uz cobsu
autoload -Uz format_python_file_black
autoload -Uz vimconfig


# INDY HYPERLEDGER
export PKG_CONFIG_ALLOW_CROSS=1
export CARGO_INCREMENTAL=1
export RUST_LOG=indy=trace
export RUST_TEST_THREADS=1

export OPENSSL_DIR=/opt/homebrew/opt/openssl
export OPENSSL_LIB_DIR=/opt/homebrew/opt/openssl/include
export OPENSSL_INCLUDE_DIR=/opt/homebrew/opt/openssl/lib


export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion


export OPENSSL_DIR=$(brew --prefix openssl)
export OPENSSL_LIB_DIR=$(brew --prefix openssl)/lib
export OPENSSL_INCLUDE_DIR=$(brew --prefix openssl)/include

export PATH="/Users/carlosegat/platform-tools:$PATH"
export PATH="$PATH:$(go env GOPATH)/bin"

export ipfs_data="/Users/carlosegat/ipfs_data"
export ipfs_staging="/Users/carlosegat/ipfs_staging"

export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$HOME/.local/bin:$PATH"
export EDITOR="nvim"

# open yazi with y and cd where you exit
function y() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
    yazi "$@" --cwd-file="$tmp"
    if cwd="$(cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
        builtin cd -- "$cwd"
    fi
    rm -f -- "$tmp"
}

# Search TEXT from Git Root
function sf() {
  # Find the git root, fallback to current dir if not in a repo
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")

  echo "Searching text in: $root"

  selected=$(rg --line-number --column --color=always "." "$root" | \
    fzf --ansi --delimiter : \
        --preview 'bat --color=always --highlight-line {2} {1}' \
        --preview-window '~3,+{2}+3/2')

  [ -n "$selected" ] && nvim $(echo "$selected" | cut -d: -f1) +$(echo "$selected" | cut -d: -f2)
}

# Find FILES from Git Root
function ff() {
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")

  echo "Finding files in: $root"

  # fd automatically respects .gitignore by default!
  selected=$(fd . "$root" --type f | fzf --preview 'bat --color=always {}')

  [ -n "$selected" ] && nvim "$selected"
}

eval "$(zoxide init zsh)"

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.config/p10k/p10k.zsh ]] || source ~/.config/p10k/p10k.zsh
