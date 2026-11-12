export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1
export HYPRLAND_INSTANCE_SIGNATURE=$(ls $XDG_RUNTIME_DIR/hypr | head -1)
for fmt in abgr rgb bgr; do
  pkill -x awww-daemon; sleep 1
  (setsid awww-daemon --format $fmt >/tmp/awd-$fmt.log 2>&1 &); sleep 2
  awww clear ff0000 >/dev/null 2>&1; sleep 2
  grim /tmp/f-$fmt.png 2>/dev/null; echo "$fmt shot taken"
done
