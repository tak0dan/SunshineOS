# Sunshine OS fish (Plasma session). The Hyprland desktop replaces this file with end-4's config at install time.
set -g fish_greeting
if status is-interactive
    command -sq starship; and starship init fish | source
    command -sq fastfetch; and fastfetch
end
