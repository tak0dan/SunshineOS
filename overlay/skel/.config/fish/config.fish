# Sunshine OS fish (Plasma session). The Hyprland desktop replaces this file with end-4's config at install time.
set -g fish_greeting
if status is-interactive
    command -sq starship; and starship init fish | source
    command -sq fastfetch; and fastfetch
    if command -sq lsd
        alias ls 'lsd --group-dirs first'
        alias ll 'lsd -l --group-dirs first'
        alias la 'lsd -la --group-dirs first'
        alias lt 'lsd --tree --depth 2'
    end
end
