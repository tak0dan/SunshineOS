# Sunshine OS zsh configuration
export EDITOR=nano
export VISUAL=nano
export BROWSER=zen-browser
export PATH="$HOME/.local/bin:$HOME/Applications:$PATH"
HISTFILE=~/.zsh_history; HISTSIZE=20000; SAVEHIST=40000
setopt HIST_IGNORE_ALL_DUPS SHARE_HISTORY AUTO_CD INTERACTIVE_COMMENTS
autoload -Uz compinit && compinit -d ~/.cache/zcompdump
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
bindkey -e
[ -f /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ] && source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
command -v starship >/dev/null && eval "$(starship init zsh)"
command -v zoxide   >/dev/null && eval "$(zoxide init zsh --cmd cd)"
if command -v lsd >/dev/null; then
  alias ls='lsd --group-dirs first'; alias ll='lsd -l --group-dirs first'; alias la='lsd -la --group-dirs first'; alias lt='lsd --tree --depth 2'
fi
command -v bat >/dev/null && alias cat='bat --paging=never --style=plain'
alias update='sunshine-update'; alias store='sunshine-store'
alias install='sudo pacman -S'; alias remove='sudo pacman -Rns'; alias search='pacman -Ss'; alias aur='paru -S'
[ -f /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ] && source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
