 # Shared look of the Sunshine tools (source it):  . /usr/local/lib/sunshine/ui.sh
 # say / ok / bad / sec           coloured lines (warm wording when cozy=on, night wording from 22:00 to 08:00)
 # t KEY                          the text for KEY in the selected language
 # sun_run "label" command...     runs a command behind an animated graph; on success the Sunshine OS logo animation, on failure the output and a fix hint (no animation)
 # sun_exec_priv cmd...           re-exec a tool with terminal sudo when started from a terminal, polkit only from a launcher
 [ -n "${SUN_UI_LOADED:-}" ] && return 0; SUN_UI_LOADED=1
 SUN_CONF_SYS=/etc/sunshine/tools.conf; SUN_CONF_USER=${XDG_CONFIG_HOME:-${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)/.config}}; SUN_CONF_USER=${SUN_CONF_USER:-$HOME/.config}/sunshine/tools.conf
 sun_conf() { local v; for f in "$SUN_CONF_USER" "$SUN_CONF_SYS"; do [ -r "$f" ] && v=$(sed -n "s/^$1=//p" "$f" | tail -1) && [ -n "$v" ] && { printf '%s' "$v"; return; }; done; printf '%s' "$2"; }
 SUN_COZY=$(sun_conf cozy on); SUN_ANIM=$(sun_conf animation on); SUN_LANG=$(sun_conf language auto)
 SUN_GRAPH=$(sun_conf graph auto); SUN_NIGHT_MODE=$(sun_conf night auto)
 SUN_FIX_HINT=${SUN_FIX_HINT:-"Check the output above; sunshine-doctor --fix repairs what is safe."}
 # Night: 22:00-08:00 local time, or forced with night=on/off in tools.conf. The site's tools demo has the same switch.
 SUN_NIGHT=0
 case "$SUN_NIGHT_MODE" in
   on) SUN_NIGHT=1 ;;
   off) SUN_NIGHT=0 ;;
   *) h=$(date +%H 2>/dev/null); if [ -n "$h" ] && { [ "$h" -ge 22 ] || [ "$h" -lt 8 ]; }; then SUN_NIGHT=1; fi ;;
 esac
 if [ "$SUN_LANG" = auto ]; then
   case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in uk*) SUN_LANG=uk ;; *) SUN_LANG=en ;; esac
   grep -qi '^city=.*toulouse' /etc/sunshine/install-location 2>/dev/null && SUN_LANG=uk
 fi
 declare -A T
 if [ "$SUN_LANG" = uk ] && [ -r ${SUNSHINE_I18N:-/usr/share/sunshine/i18n}/uk.tsv ]; then
   while IFS=$'\t' read -r _k _v; do [ -n "$_k" ] && T[$_k]=$_v; done < ${SUNSHINE_I18N:-/usr/share/sunshine/i18n}/uk.tsv
 fi
 # loc "English text": exact match, or a "prefix*" entry (the rest of the text, usually a value, is kept)
 loc() { local s=$* k; [ "$SUN_LANG" = en ] && { printf '%s' "$s"; return; }
   if [ -n "${T[$s]+x}" ]; then printf '%s' "${T[$s]}"; return; fi
   for k in "${!T[@]}"; do [[ $k == *'*' ]] && [[ $s == "${k%\*}"* ]] && { printf '%s%s' "${T[$k]%\*}" "${s#"${k%\*}"}"; return; }; done
   printf '%s' "$s"; }
 t() { local k=$1; [ -n "${T[$k]+x}" ] && printf '%s' "${T[$k]}" || printf '%s' "${2:-$1}"; }
 B=$'\e[1m'; Y=$'\e[38;5;220m'; O=$'\e[38;5;208m'; G=$'\e[32m'; R=$'\e[31m'; D=$'\e[2m'; N=$'\e[0m'
 # rose-pine pastel blue + pink for the night logo and the night messages
 PINE=$'\e[38;2;156;207;216m'; ROSE=$'\e[38;2;234;154;151m'; IRIS=$'\e[38;2;196;167;231m'
 OKC=$G; BADI='✘ 🫖'; [ "$SUN_NIGHT" = 1 ] && { OKC=$PINE; BADI='✘ 🌑'; }
 _cozy() { [ "$SUN_COZY" = on ] && printf '%s' "$1" || printf '%s' "$2"; }
 _sun_night_notice() { [ "${_SUN_NOTICED:-0}" = 0 ] || return 0; [ "$SUN_COZY" = on ] && [ "$SUN_NIGHT" = 1 ] || return 0
   _SUN_NOTICED=1; printf '%s%s %s%s\n' "$IRIS" '🌙' "$(t cozy_done_night 'You really should rest now. Take a good care of your health 🌙💤')" "$N"; }
 sec() { _sun_night_notice; printf '\n%s%s %s%s\n' "$Y$B" "$(_cozy ☀ 🌙)" "$(loc "$*")" "$N"; }
 say() { sec "$@"; }
 ok()  { printf '%s%s %s%s\n' "$OKC" "$(_cozy '✔ ☕' '✧ 🌙')" "$(loc "$*")" "$N"; }
 bad() { printf '%s%s %s%s\n' "$R" "$BADI" "$(loc "$*")" "$N"; }
 cozy_done() { [ "$SUN_COZY" = on ] || return 0
   if [ "$SUN_NIGHT" = 1 ]; then printf '%s\n' "$IRIS$(t cozy_done_night 'You really should rest now. Take a good care of your health 🌙💤')$N"
   else printf '%s\n' "$Y$(t cozy_done 'All done. Have a warm cup of tea and enjoy the sunshine ☀️🍵')$N"; fi; }

 # Privilege elevation: a tool started in a terminal asks for the password IN that terminal (sudo); only a launcher/desktop entry uses polkit.
 sun_is_tty() { [ -t 0 ] && [ -t 1 ]; }
 sun_priv() { [ "$(id -u)" -eq 0 ] && return 0; if sun_is_tty; then printf 'sudo'; else printf 'pkexec'; fi; }
 sun_exec_priv() { if [ "$(id -u)" -eq 0 ]; then exec "$@"; fi
   if sun_is_tty; then exec sudo "$@"; fi
   exec pkexec "$@"; }

 # One frame of the progress graph. Four graphs (bars, wave, equalizer, pulse) cycle in auto mode;
 # graph=bars|wave|eq|pulse in tools.conf picks one. Each graph is a moving window, not a spinner.
 _sun_graph_frame() {
   local i=$1 w=${2:-12} mode=${3:-$SUN_GRAPH} k g=''; local -a h
   if [ "$mode" = auto ] || [ -z "$mode" ]; then mode=$(( (i / 16) % 4 + 1 )); fi
   case "$mode" in
     bars|1) h=(▁ ▂ ▃ ▄ ▅ ▆ ▇ █ ▇ ▆ ▅ ▄ ▃ ▂) ;;
     wave|2) h=(∿ ∽ ≈ ∿ ~ ≋ ~ ∿ ∽ ≈ ∿ ~ ≋ ~) ;;
     eq|3)   h=(▁ ▂ ▄ ▆ █ ▆ ▄ ▂ ▁ ▃ ▅ ▇ ▅ ▃ ▁) ;;
     *)      h=(· ∘ ○ ◌ ◎ ● ◉ ◎ ◌ ○ ∘ · ● ◉ ○) ;;
   esac
   for ((k=0; k<w; k++)); do g+=${h[$(( (i + k*3 + (k%4)*2) % ${#h[@]} ))]}; done
   printf '%s' "$g"
 }
 _tool_message() { case ${0##*/} in
   sunshine-update-run) loc "System updated" ;;
   sunshine-upgrade) loc "Upgrade done" ;;
   sunshine-migrate) loc "Migration done" ;;
   sunshine-sanity) loc "Sanity passed" ;;
   sunshine-health) loc "Health checked" ;;
   sunshine-repair) loc "Repair assessed" ;;
   sunshine-rescue) loc "Rescue assessed" ;;
   sunshine-report) loc "Report ready" ;;
   sunshine-restore-visuals) loc "Visuals restored" ;;
   sunshine-fix-pacman) loc "Package manager repaired" ;;
   *) loc "All done" ;;
 esac; }

 # The Sunshine OS logo animation - the same sprite frames the website plays. On success the middle text
 # changes from "Sunshine OS" to the tool-specific message; on failure nothing is animated (see sun_run).
 # Night mode uses the rose-pine pastel blue/pink palette instead of the day gold/orange one.
 sun_success_anim() {
   [ "$SUN_ANIM" = on ] && [ -t 1 ] || return 0
   local p=/usr/share/sunshine/logo-anim/play.py msg=${1:-${SUN_SUCCESS_MSG:-}} args=(--tool --lite --max-text=15)
   [ -n "$msg" ] || msg=$(_tool_message)
   [ -n "$msg" ] && args+=("--title=$msg")
   [ "$SUN_NIGHT" = 1 ] && args+=(--night)
   # Old players ignore unknown flags: without --tool support they would run the endless site animation and hang the tool.
   # Only use the sprite player when it actually supports tool mode, and bound it with a timeout as a second guard.
   if [ -r "$p" ] && command -v python3 >/dev/null 2>&1 && grep -q -- '--tool' "$p" 2>/dev/null; then
     local runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 15'
     $runner python3 "$p" "${args[@]}" 2>/dev/null && return 0
   fi
   # fallback when the sprite player is missing or too old: a small coloured logo line, still no animation on failure
   printf '%s☀%s  %s\n' "$([ "$SUN_NIGHT" = 1 ] && printf '%s' "$PINE" || printf '%s' "$Y")" "$N" "$(loc "$msg")"
 }
 sun_run() {            # sun_run "label" cmd args...
   local label=$1; shift; local log rc pid i=0 t0 st
   log=$(mktemp)
   if [ "$SUN_ANIM" != on ] || ! [ -t 1 ]; then printf '%s ...\n' "$label"; "$@" >"$log" 2>&1; rc=$?
     if [ $rc -eq 0 ]; then ok "$label"; else bad "$label"; [ -n "$SUN_FIX_HINT" ] && printf '  %s%s%s\n' "$D" "$(loc "$SUN_FIX_HINT")" "$N"; tail -n 20 "$log"; fi
     rm -f "$log"; return $rc; fi
   "$@" >"$log" 2>&1 & pid=$!; t0=$(date +%s)
   printf '\e[?25l'
   while kill -0 "$pid" 2>/dev/null; do
     st=$(_sun_graph_frame "$i")
     printf '\r%s%s%s %s  %ss' "$OKC" "$st" "$N" "$label" "$(( $(date +%s) - t0 ))"
     i=$((i + 1)); sleep 0.09
   done
   wait "$pid"; rc=$?; printf '\r\e[K\e[?25h'
   if [ $rc -eq 0 ]; then ok "$label"
   else bad "$label"; [ -n "$SUN_FIX_HINT" ] && printf '  %s%s%s\n' "$D" "$(loc "$SUN_FIX_HINT")" "$N"; tail -n 20 "$log"; fi
   rm -f "$log"; return $rc
 }

 # ---- internet check: several independent methods, so one blocked protocol never means "no internet" (ping alone is dropped by many networks,
 # virtual machines and firewalls). sun_online returns 0 when ANY method works and sets SUN_NET_METHOD to the one that did; on failure SUN_NET_WHY
 # says where it stops (link, route, DNS, HTTP, captive portal) so the message can be specific. sun_online_quick uses only the first method.
 sun_online_quick() { curl -fsI --max-time "${1:-6}" https://archlinux.org >/dev/null 2>&1; }
 sun_online() {
   SUN_NET_METHOD=; SUN_NET_WHY=
   local code body u
   # 1. the main test: an HTTPS request to the package site (works through proxies and everything a browser can reach)
   if sun_online_quick 6; then SUN_NET_METHOD="HTTPS archlinux.org"; return 0; fi
   # 2. the Arch mirror network and a second host, plain HTTP and HTTPS (a different server, different port)
   for u in https://geo.mirror.pkgbuild.com/ http://geo.mirror.pkgbuild.com/ https://www.gnu.org/; do
     if curl -fsI --max-time 6 "$u" >/dev/null 2>&1; then SUN_NET_METHOD="HTTP(S) $u"; return 0; fi
   done
   # 3. the connectivity-check pages browsers use: HTTP 204 = free internet; a redirect (30x) means a captive portal (a login page)
   for u in http://connectivity-check.ubuntu.com/ https://www.gstatic.com/generate_204 http://nmcheck.gnome.org/check_network_status.txt; do
     code=$(curl -s -o /dev/null --max-time 6 -w '%{http_code}' "$u" 2>/dev/null)
     case "$code" in 204) SUN_NET_METHOD="connectivity check $u"; return 0;; 30*) SUN_NET_WHY=portal;; esac
   done
   [ "$SUN_NET_WHY" = portal ] && return 1
   # 4. NetworkManager's own verdict
   if command -v nmcli >/dev/null 2>&1 && [ "$(nmcli -t networking connectivity check 2>/dev/null)" = full ]; then SUN_NET_METHOD="NetworkManager says full"; return 0; fi
   # 5. a raw TCP connection to public addresses (no DNS, no HTTP): proves the route works even if names do not resolve
   for u in 1.1.1.1:443 8.8.8.8:53 9.9.9.9:443; do
     if timeout 4 bash -c "exec 3<>/dev/tcp/${u%:*}/${u#*:}" 2>/dev/null; then SUN_NET_METHOD="TCP $u"; SUN_NET_WHY=dns-or-http; return 0; fi
   done
   # 6. last resort: ping
   for u in 1.1.1.1 8.8.8.8; do if ping -c1 -W3 "$u" >/dev/null 2>&1; then SUN_NET_METHOD="ping $u"; return 0; fi; done
   # nothing worked: find out where it stops
   if ! ip -4 route 2>/dev/null | grep -q '^default'; then SUN_NET_WHY=route
   elif ! getent hosts archlinux.org >/dev/null 2>&1; then SUN_NET_WHY=dns
   else SUN_NET_WHY=blocked; fi
   return 1
 }
 sun_net_explain() {   # a sentence for the user after sun_online failed
   case "${SUN_NET_WHY:-}" in
     route) loc "This computer is not connected to a network (no route). Connect to Wi-Fi or a cable and try again.";;
     dns) loc "Connected, but names do not resolve (DNS). Try: sunshine-fix network";;
     portal) loc "A login page (captive portal) is blocking the internet: open a browser and sign in to the network first.";;
     blocked) loc "A network is there but web requests do not get through (firewall, proxy or VPN?).";;
     *) loc "No internet connection. Connect to Wi-Fi or a cable and try again.";;
   esac
 }
