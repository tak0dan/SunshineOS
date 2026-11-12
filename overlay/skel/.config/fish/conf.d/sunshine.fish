# Sunshine OS additions (end-4's config.fish, with the Sunshine patch, already sets up the prompt and the greeting)
set -gx EDITOR nano
set -gx VISUAL nano
set -gx BROWSER (command -sq zen-browser; and echo zen-browser; or echo firefox)
fish_add_path -g $HOME/.local/bin $HOME/Applications

if status is-interactive
    command -sq zoxide; and zoxide init fish --cmd cd | source
    command -sq fzf;    and fzf --fish | source 2>/dev/null
    if command -sq lsd
        alias ls 'lsd --group-dirs first'
        alias ll 'lsd -l --group-dirs first'
        alias la 'lsd -la --group-dirs first'
        alias lt 'lsd --tree --depth 2'
    end
    command -sq bat; and alias cat 'bat --paging=never --style=plain'
    abbr -a update   sunshine-update
    abbr -a store    sunshine-store
    abbr -a install  'sudo pacman -S'
    abbr -a remove   'sudo pacman -Rns'
    abbr -a search   'pacman -Ss'
    abbr -a aur      'paru -S'
    abbr -a ..       'cd ..'
    abbr -a ...      'cd ../..'
    abbr -a gs       'git status'
end
