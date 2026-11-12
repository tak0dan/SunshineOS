# Sunshine OS bash configuration
[[ $- != *i* ]] && return

export EDITOR=nano
export VISUAL=nano
export BROWSER=zen-browser
export PATH="$HOME/.local/bin:$HOME/Applications:$PATH"
HISTSIZE=20000; HISTFILESIZE=40000; HISTCONTROL=ignoreboth:erasedups
shopt -s histappend checkwinsize autocd 2>/dev/null

[ -r /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion
command -v starship >/dev/null && eval "$(starship init bash)"
command -v zoxide   >/dev/null && eval "$(zoxide init bash --cmd cd)"

if command -v eza >/dev/null; then
  alias ls='eza --icons --group-directories-first'; alias ll='eza -l --icons --group-directories-first --git'; alias la='eza -la --icons'
else
  alias ls='ls --color=auto'; alias ll='ls -lh --color=auto'
fi
command -v bat >/dev/null && alias cat='bat --paging=never --style=plain'
alias update='sunshine-update'; alias store='sunshine-store'
alias install='sudo pacman -S'; alias remove='sudo pacman -Rns'; alias search='pacman -Ss'; alias aur='paru -S'
alias ..='cd ..'; alias ...='cd ../..'; alias grep='grep --color=auto'
