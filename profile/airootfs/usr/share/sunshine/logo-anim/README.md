# Sunshine OS logo animation

Pixel-art build-up of the logo plus a 10 s idle loop. `play.py --lite --splash` plays the build-up and returns to the prompt;
without `--splash` it keeps looping until a key is pressed. It renders through the kitty graphics protocol (kitty), sixel
(foot, konsole, ...) or half-block characters (any truecolor terminal) and picks the renderer by itself.
Needs python3 with Pillow and numpy. Normally started through `sunshine-term` / `sunshine-session`.
