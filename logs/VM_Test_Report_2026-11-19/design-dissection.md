# Design dissection — Sunshine OS 13.4.7.1.5

**Scope:** visual identity, theme system, icons, typography, layout, copy, installer/store surfaces, accessibility, and the specific “action icons are too dark in Konsole/Kate” feedback.

---

## 1. Design thesis

Sunshine OS has a clear idea: **warm sunlight on dark graphite**. Amber/orange accents, near-black navy backgrounds, a sun/flower motif, and a friendly, slightly “cozy” voice (`☕`, tea, “Have a warm cup of tea”). It is not a stock KDE reskin; the wallpaper, panel, icons, SDDM, GRUB and Calamares all carry the same identity.

That is the strongest part of the product. The weaknesses are not taste — they are **delivery and consistency**: GTK apps fall out of the theme, some symbolic icons lose contrast, and a few consumer-cute choices do not scale to a managed fleet.

---

## 2. What works

### 2.1 Colour and atmosphere

- `SunshineDark` uses `#151729` / `#0B1020` backgrounds with warm `#F4F0EB` text and `#E87932` / `#F5A442` accents.
- The result is warmer and more distinctive than the usual blue-grey dark themes; it reads well in screenshots and gives the product a memorable identity.
- The accent is used for focus/selection, not sprayed everywhere, which keeps the desktop calm.

### 2.2 Qt/Plasma surface is coherent

- `SunshineDark` colour scheme, `Sunshine` desktop theme, Kvantum `Sunshine` widget style, Aurorae `Sunshine` window decoration, `Sunshine-orange-dark` icons, and the Sunshine SDDM theme.
- Window buttons are on the right (`ButtonsOnRight IAX`) — a deliberate Windows-like spatial language.
- The panel is a 48 px full-width bar with centred app icons and a right-side tray/clock: familiar to Windows 11 users, low training cost.

### 2.3 Branded boot and installer

- GRUB theme at `/usr/share/grub/themes/sunshine/`.
- SDDM theme `sunshine`.
- Calamares branding exists and opens with the dark/amber palette.
- This continuity from firmware → boot → login → desktop is rare in small distros and is a genuine polish win.

### 2.4 Friendly copy

The tools speak human: “All good”, “Have a warm cup of tea”, “go back from the boot menu if anything breaks”. For home/SMB users this lowers fear. It is a deliberate tone choice, not an accident.

---

## 3. The action-icon problem (user feedback)

**Feedback recorded:** *“Icons for the actions in Plasma apps like Konsole or Kate, not everywhere — too dark; maybe white or very light pastel blue will be better.”*

This is a precise and valid observation. It is **not** a request to replace the whole icon theme. It is about toolbar/action icons inside KDE applications.

### 3.1 What the assets say

The action SVGs in `Sunshine-orange-dark` use `currentColor` with a light fallback:

```xml
<style id="current-color-scheme" type="text/css">
  .ColorScheme-Text { color:#dedede; }
</style>
<path ... style="fill:currentColor" class="ColorScheme-Text"/>
```

Rendered on white, `document-open.svg` has a mean luminance of **0.967** — i.e. the source icon is nearly white, not dark. The colour scheme's `ForegroundNormal` is `244,240,235` and the Kvantum `button.text.color` is `#f4f0eb`. So the **global palette is not the cause**.

### 3.2 Likely causes of the perceived darkness

1. **Inactive-window dimming.** KDE dims toolbar icons when the window is not active. A 16 px symbolic icon at ~40–60 % opacity on `#141525` reads as dark grey. In the captured Kate screenshot, the toolbar background is `#141525` (luma ≈ 21) and the dominant non-background icon pixels are around `#6F6F76` (luma ≈ 111), not `#DEDEDE`.
2. **16 px toolbar icons.** Kvantum sets `toolbar_icon_size=16`, `button_icon_size=16`. At 1280×800 and 1× scale, 16 px thin-stroke icons lose contrast; on HiDPI they may be scaled with blur.
3. **Merged menubar + toolbar.** `merge_menubar_with_toolbar=true` puts text and icons in one dense band; there is less visual separation and the eye reads the icons as part of the dark chrome.
4. **Disabled/inactive state opacity.** `disabled_icon_opacity=100` in Kvantum is not the issue, but Qt's inactive palette and the “window not focused” state still dim the whole toolbar.
5. **Specific multicolour icons** (e.g. exit/close) use a dark red `#DA4453`; on a dark background these read darker than the neutral icons.

### 3.3 Recommended fix (targeted, not a theme swap)

Introduce a dedicated **action-icon foreground token** and apply it to symbolic action icons in Plasma/KDE apps:

| Token | Value | Use |
|---|---|---|
| `ActionIconNormal` | `#EAF2FF` (very light pastel blue) | Default toolbar/action icons |
| `ActionIconHover` | `#FFFFFF` | Hover/focus |
| `ActionIconPressed` | `#FFD27A` (warm amber) | Pressed/checked |
| `ActionIconDisabled` | `#8F93A6` | Disabled, still ≥ 3:1 on `#141525` |

Implementation options, in order of preference:

1. **Theme-level:** add a `ColorScheme-Text` override for `actions` in the Sunshine icon theme so symbolic action icons render at `#EAF2FF`, independent of the window active state; keep app-launcher icons orange.
2. **Kvantum-level:** set `toolbar_icon_size=18` or `20`, `button_icon_size=18`, and ensure `PanelButtonTool`/`ToolbarButton` text/icon colours use the token.
3. **KDE colour-scheme-level:** verify `[Colors:Button] ForegroundNormal` and `[Colors:Window] ForegroundNormal` are used for icon recolouring in Konsole/Kate; if the apps use `QPalette::ButtonText`, keep it light (`#F4F0EB`) and do not let the inactive group fall below `#B8BDCC`.
4. **Per-app test:** Konsole toolbar (new tab, split, copy, paste), Kate toolbar (new, open, save, undo, redo, find), Dolphin (back/forward, view modes), and the window decoration buttons.

**Why pastel blue rather than pure white:** pure white maximises contrast but can look harsh on a warm amber/graphite identity; `#EAF2FF` keeps the warm/cool balance and reads as “light” without competing with the amber accent. Offer both: default `#EAF2FF`, high-contrast `#FFFFFF`.

### 3.4 Acceptance test

- Open Konsole and Kate in an **active** window on the default dark theme.
- Measure the icon pixels: target mean luminance ≥ 200 on `#141525` (contrast ≥ 10:1 for normal icons).
- Repeat in an **inactive** window: target ≥ 150 (contrast ≥ 6:1), not the current ~111.
- Verify at 100 %, 125 %, 150 % and 200 % scaling.
- Verify hover, pressed, checked and disabled states.

---

## 4. Theme-system consistency

### 4.1 The Qt/GTK split

The installed system reports:

```text
Qt:  Sunshine (Dark) / Sunshine-orange-dark
GTK: Breeze-Dark / Sunshine-orange-dark
```

There is **no Sunshine GTK theme** in `/usr/share/themes` (only Breeze, Breeze-Dark, Default, Emacs). GTK apps therefore inherit a dark Breeze look with Sunshine icons, not the Sunshine widget language. Firefox, Calamares internals, file dialogs and third-party GTK apps visibly break the identity.

**Fix:** ship a minimal GTK3/GTK4 theme (or a libadwaita `gtk.css` + matched `gtk-3.0` CSS) using the same palette and 6–8 px radii as Kvantum; add it to `/etc/skel` and the offline restore path. At minimum, generate GTK CSS from the same colour tokens as `SunshineDark.colors` so the two cannot drift.

### 4.2 Offline restore overpromises

`sunshine-restore-visuals --offline` says “visuals restored” even when `plasma-apply-colorscheme` / `plasma-apply-desktoptheme` abort because there is no display. In a real session it applies; in a headless/SSH/automation context it should detect the missing `DISPLAY`/`WAYLAND_DISPLAY` and say “skipped: no graphical session”, not claim success.

### 4.3 Live vs installed fastfetch mismatch

The live session reported `breeze-dark [Qt]` while GTK reported `Sunshine-orange-dark`; the installed system reports Sunshine for both. This suggests an ordering issue in the live plasma setup/restore path. It is not visible in the installed product, but it undermines demo screenshots.

---

## 5. Typography

- **Noto Sans 10 pt** is a safe, neutral choice with broad coverage; Noto Sans Mono for the terminal.
- It is not distinctive, but it is the right trade-off for an international product: no licensing risk, good hinting, wide script coverage.
- **Gap:** `noto-fonts-cjk` is not installed, so Chinese/Japanese/Korean text may show tofu. For an enterprise with global staff, this is a functional bug, not a taste issue.
- **Opportunity:** use a slightly larger default (10.5–11 pt) for 1080p business laptops; 10 pt is compact and can feel cramped in dialogs.
- **Terminal:** fish + Starship is friendly, but Starship can stall on large directories (`Scanning current directory timed out`). Set a timeout or use a simpler prompt for the default shell.

---

## 6. Layout and panel

### What works

- 48 px full-width panel, centred apps, right tray: instantly familiar to Windows 11 users.
- Custom plasmoids for active window title and live network/disk/CPU/GPU graphs add information density without a separate app.
- The dark panel with amber highlights is visually distinct.

### What is questionable

- **Windows 11 pastiche.** Centred icons + right tray + 48 px is a direct copy. It lowers switching cost, but it also invites “this is a Windows clone” comparisons and gives up the chance to define a Sunshine interaction model.
- **Dense top bar.** Window title + graphs + tray + clock in 48 px can feel busy on 1280×800; on a 1366×768 business laptop it will be tighter.
- **Panel configuration lives in a long inline QML `evaluateScript` string.** It is hard to review, version, diff and test. Move it to a versioned QML file/plasmoid package.
- **No documented fallback** for Plasma changes or VMs without 3D; the Sunshine session has a safety net, but the panel layout has no “safe mode”.

**Recommendation:** keep the familiar layout as the default, but add a **“Sunshine Compact”** panel preset (left-aligned apps, smaller height, optional graphs) and a **“Focus”** preset (minimal bar). Offer them in Welcome/Toolbox; enterprises can choose one via policy.

---

## 7. Copy and tone

### Good

- Human, calm, non-blaming error text.
- “Restore points are made automatically before and after the update” explains the safety net in one sentence.
- Arch-news gate (“manual intervention required”) treats the user as an adult.

### Questionable

- **Cozy copy in system-critical paths.** “Have a warm cup of tea” after a repair is charming for home users, but in a managed fleet or a failed update it can read as flippant. Provide a **professional copy set** for the business image (same meaning, no emoji/coffee).
- **“Apps you chose”** in the updater is ambiguous if the user never explicitly chose apps (first-update defaults). Say “Installing the apps included with Sunshine (LibreOffice, Zen)” and show size/time.
- **Mixed languages.** The tools include Ukrainian strings, but the OS locale is only `en_US`. Either complete the localization or keep the UI English-only; half-localized is worse than either.

---

## 8. Installer, Welcome, Toolbox, Store

### Calamares

- Opens with the Sunshine brand, dark/amber palette, and a clear “Install Sunshine OS / Put Sunshine OS on this computer” choice.
- The old fatal `$p` error is structurally gone; the module now calls `/usr/local/bin/sunshine-register-base`.
- **Weakness:** the error dialog path is still stock Qt; if an install step fails, the bright/default dialog breaks the dark language exactly when the user is stressed. Theme the Calamares error/confirm dialogs and add a “copy diagnostic bundle” button.
- **Weakness:** the partition legend and some controls have had contrast fixes; verify on light and dark backgrounds and at 125 % scaling.

### Welcome

- Clear tiles: install, repair, visuals, apps, drivers, battery/noise.
- **Weakness:** dense; the hierarchy between “install” and “learn” is not obvious. On first boot, make **Install** the single primary action and collapse the rest into “Explore”.
- **Weakness:** the “egg” easter egg (“An egg appeared! Keep the app running”) is charming but can confuse a first-time business user; hide it behind “About” or a long-press.

### Toolbox

- Good concept: one place for repair, snapshots, drivers, themes, apps.
- **Weakness:** too many equally weighted actions; add a “Recommended” section and a search field.
- **Weakness:** destructive actions (reset Plasma, restore visuals, repair boot) need a clear impact statement and a confirmation with a snapshot reminder.

### Store

- Strong visual shell; curated categories (Installed, Windows, Web apps, Flatpak/AppImage/Snap/Wine) are a good story.
- **Weakness:** first-run “Pick anything that sounds like you” is consumer onboarding; in a managed fleet it is noise. Add “Managed by IT — skip”, and let policy pin a catalogue subset.
- **Weakness:** first load is heavy and shows “Preparing the app catalog…” without progress detail; add a determinate progress/size or a skeleton.
- **Weakness:** `--help` is not implemented and headless invocation can dump core; CLI parity matters for automation.

---

## 9. Accessibility and contrast

| Item | Status | Recommendation |
|---|---|---|
| Screen reader | **Missing** (no Orca/speech-dispatcher) | Ship `orca` + `speech-dispatcher` in a11y meta; test Plasma. |
| Magnifier | Missing | Add `kmag`/KDE magnifier to a11y meta. |
| On-screen keyboard | Missing | Add `maliit`/KDE virtual keyboard. |
| Keyboard navigation | Plasma default is good | Test Calamares, Welcome, Toolbox, Store with keyboard only; visible focus rings. |
| Colour contrast | Body text good; disabled/inactive icons weak | Fix action-icon tokens (section 3); target WCAG AA for normal text (4.5:1), 3:1 for large/UI. |
| Scaling | 16 px toolbar icons at 1× are small | 18–20 px toolbar icons; test 125–200 %. |
| Motion | `kwin` animations are disabled in the VM-safe path | Respect “reduce motion”; do not rely on animation to convey state. |
| Fonts | No CJK | Add `noto-fonts-cjk`; test Arabic/Hebrew/Devanagari. |

**Contrast check (approx.):**

- `#F4F0EB` on `#151729`: ~15:1 — excellent.
- `#E87932` on `#151729`: ~6.5:1 — good for large text/UI.
- `#AAA3A0` (inactive) on `#151729`: ~6.5:1 — okay.
- `#69636A` (disabled) on `#24202A`: ~2.2:1 — below AA, but disabled text is exempt; still consider `#8F93A6`.
- `#6F6F76` (observed icon pixels) on `#141525`: ~4.1:1 — below the 4.5:1 target for normal text and visually “dark”; this is the user’s complaint quantified.

---

## 10. Poor or questionable decisions (design/UX)

1. **No Sunshine GTK theme.** The Qt side is branded; GTK apps are not. This is the largest visible inconsistency.
2. **Action icons rely on `currentColor` + inactive dimming at 16 px.** On dark toolbars they fall to ~4:1 and read as dark. Fix with a dedicated token and larger toolbar icons.
3. **Windows 11 panel pastiche.** Familiar, but derivative; no unique Sunshine interaction model.
4. **Consumer-cute copy in critical paths.** “Warm cup of tea” after a repair is charming at home and odd in a fleet; provide a professional copy set.
5. **Store onboarding assumes a personal user.** “Pick anything that sounds like you” has no “managed by IT” path.
6. **Installer error dialogs are unthemed.** The worst moment breaks the brand.
7. **Offline restore claims success without a display.** It should detect and report “skipped”.
8. **GPU/CPU/network graphs in the default panel.** Nice for enthusiasts; noise for task workers. Make them optional presets.
9. **Only a dark theme is applied by default.** A light variant exists (`Sunshine-orange-light`) but there is no obvious system toggle or enterprise policy.
10. **Cursor remains `breeze_cursors`.** The identity stops at the pointer.
11. **Exact-version icon-font dependency.** Doctor warns if `ttf-material-symbols-variable` changes because Hyprland icons become “odd letters”; bundle the font or provide a fallback map.
12. **Emoji/coffee in terminal output.** Rendering varies by font/terminal; in SSH/logs it can become tofu. Use plain text in logs, emoji only in the interactive UI.
13. **First-run density.** Welcome/Toolbox/Store all compete for attention; define one primary path (Install → Update → Apps) and hide the rest.
14. **No high-contrast variant.** Add a “Sunshine High Contrast” colour scheme and icon variant; it also helps accessibility compliance.

---

## 11. Prioritized design fixes

| Priority | Fix | Effort | Impact |
|---|---|---|---|
| P0 | Action-icon token `#EAF2FF`, 18–20 px toolbar icons, verify Konsole/Kate/Dolphin active + inactive | S | Fixes the reported complaint; large perceived-quality gain |
| P0 | Ship a minimal Sunshine GTK3/GTK4 theme (or generated CSS) in `/etc/skel` and offline restore | M | Removes the biggest visual break |
| P1 | Theme Calamares error/confirm dialogs; add “copy diagnostics” | S | Protects the brand at the worst moment |
| P1 | Professional copy set for business image; plain-text logs | S | Enterprise credibility |
| P1 | Add CJK fonts + locale selection; accessibility meta | M | Unlocks international/public-sector buyers |
| P2 | Panel presets (Default / Compact / Focus) and policy support | M | Fits task workers and enterprises |
| P2 | Store “Managed by IT” mode and catalogue pinning | M | Makes the Store fleet-friendly |
| P2 | High-contrast theme + icon variant | M | Accessibility compliance |
| P3 | Branded cursor; light-theme toggle; reduce-motion preset | S | Finish the identity |

---

## 12. Design verdict

Sunshine OS has a **real visual identity** and a **coherent Qt/Plasma execution**. It looks warmer and more intentional than most small distros. The reported “dark action icons” are a genuine contrast defect concentrated in KDE app toolbars, not a reason to replace the icon set; a pastel-blue `#EAF2FF` action token plus 18–20 px icons should fix it without losing the amber identity.

The remaining design debt is consistency and context: **GTK is not themed**, **critical dialogs are stock**, **the copy is consumer-only**, and **accessibility/i18n are incomplete**. Fix those four and the design is no longer a demo asset — it becomes a product asset that can survive an enterprise procurement review.
