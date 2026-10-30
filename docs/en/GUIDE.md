[Español](../es/GUIA.md) · **English** · [Home](../../README.md)

# User guide

Each section answers "I want to do X". Paths are those of a normal installation; folder names follow your system language (here `Videos` and `Pictures`).

> The interface is in Spanish. Names are written as they appear on screen, with the English meaning in parentheses.

## The window

It has three tabs: **Grabar** (Record), **Audio y cámara** (Audio and camera) and **Directo** (Live). The *Grabar* and *Pausar* (Pause) buttons are always at the bottom. While you record, the window hides and everything is controlled from the **tray icon** (right click) or with the shortcuts.

Next to the *Grabar* button there are: *Captura de pantalla* (Screenshot), *Modo presentación* (Presentation mode), *Herramientas de vídeo* (Video tools) and *Acerca de* (About).

## Take a screenshot

1. `Ctrl+Alt+S` (or the *Captura de pantalla* button).
2. Drag to pick a region, or press `Enter` or `Space` for the whole screen. `Esc` cancels.
3. It is saved in `Pictures/Screenshots` and copied to the clipboard, ready to paste.

The first time, the desktop asks for permission.

## Record the screen

1. In the **Grabar** tab choose:
   - **Zona al grabar** (Area to record): *Libre* (free: drag a region or the full screen) or *Vertical 9:16* (for TikTok, Shorts and Reels).
   - **Calidad** (Quality): *WhatsApp / Telegram* (small and sharp), *YouTube* (good quality) or *Máxima* (maximum, for editing later).
   - **Fotogramas** (Frame rate): 24, 30 or 60 fps.
   - **Tamaño máximo** (Maximum size): no limit, 16, 50 or 100 MB.
2. Press **Grabar** (or `Ctrl+Alt+R`) and choose the region.
3. To finish: `Ctrl+Alt+R` again, or *Detener la grabación* (Stop recording) in the tray icon.
4. The video appears in `Videos/Screen Recordings` named `grabacion-YYYYMMDD-HHMMSS.mp4`.

**Pause and resume:** `Ctrl+Alt+P` or the tray menu.

**The size reduction happens afterwards:** with *WhatsApp / Telegram* the video is saved when you stop and, in the background, reduced to 720p (it can take a few minutes for long recordings; a notification arrives when done and the file is replaced only if the result is smaller). With *YouTube* or *Máxima* nothing is reduced.

**Audio:** in the *Audio y cámara* tab tick *Audio del sistema* (system audio) and/or *Micrófono* (microphone). Each source goes on its own track and they are mixed when saving, with the volume you choose (0–200 %). For the microphone you can enable noise reduction: *suave* (soft) or *fuerte* (strong; the strong one closes the microphone between sentences and can cut very quiet word endings).

**Interrupted recordings:** if the program or the computer shuts down, what you recorded is not lost; it is recovered the next time you open the program as `grabacion-recuperada-…`.

## Yellow frame and moving the region

While you record a region, a yellow line surrounds it **on the outside** (it does not appear in the video). With it you can **drag the region while recording**: grab the line or the "arrastra para mover" (drag to move) handle. Only the line receives the mouse; the rest of the screen works as usual.

## Record vertical (TikTok, Shorts, Reels)

1. In *Zona al grabar* choose **Vertical 9:16**, or press `V` in the region selector.
2. A 9:16 frame follows the mouse: the **wheel** changes its size and a **click** fixes it.
3. Move it while recording by dragging the yellow line.

## Zoom while recording

*(KDE Plasma only.)* In *Ayudas para tutoriales* (Tutorial helpers) choose 1.5×, 2× or 2.5×. During the recording, `Ctrl+Alt+Z` zooms in centered on the cursor and again zooms out, with a smooth transition. The tray icon changes to a magnifier while zoom is active. The zoom is applied **when the recording ends** (the video is rewritten; about 0.8 s per second recorded at 1080p), so the window says "Guardando…" (Saving) for a while.

If you never press `Ctrl+Alt+Z` during the recording, the video has no zoom.

**Resaltar el cursor** (highlight the cursor: a halo around the pointer) is enabled in the same section.

## Clicks and keys on screen

To show colored ripples on every click and a pill with the keys you press:

1. Your user must be in the `input` group (the system does not allow reading mouse and keyboard otherwise). In a terminal: `sudo usermod -aG input $USER` and **log out and back in**.
2. Tick *Resaltar los clics del ratón* (highlight mouse clicks) and, in *Mostrar teclas* (show keys), choose: *No mostrar teclas* (don't show), *Solo atajos y teclas especiales* (only shortcuts and special keys: Ctrl+C, Enter, Esc…) or *Todo lo que escribo* (everything I type).

**Privacy:** it is read only while you record or stream, nothing is stored, and by default what you type is not shown. Avoid "everything I type" if you will type passwords.

## Save a clip of the last few seconds

While recording or streaming, `Ctrl+Alt+G` saves the last 15, 30, 60 or 120 seconds (chosen in *Clip con Ctrl+Alt+G*) separately in `Videos/Screen Recordings/Clips`, without stopping the recording. It is for "that thing that just happened, I want to keep it". It does not work while paused.

## Camera bubble

1. In *Audio y cámara* tick **Cámara en burbuja** (camera bubble).
2. When you record, a round bubble appears that you can **drag** around the screen.
3. **Hide and show it while recording:** `Ctrl+Alt+C`, or in the tray icon *Quitar la burbuja de la cámara* (remove the camera bubble) / *Poner la burbuja de la cámara* (put it back). Hiding it does not change your setting: the next recording has it again.
4. In the *Efectos de la cámara* (camera effects) panel (live preview): shape (circle or rounded square), border color, mirror, brightness, contrast and **green or blue background removal**.

## Presentation mode: draw on the screen

`Ctrl+Alt+D` (or the *Modo presentación* button) puts a transparent layer over the screen and a toolbar with: pen, highlighter, arrow, frame, ellipse and text (type and press `Enter`); 6 colors, 3 thicknesses, undo, clear and **click-through** (you use the desktop without leaving, and what you drew stays visible).

Keys: `1`–`6` switch tool, `Ctrl+Z` undo, `C` clear, `Space` toggles click-through, `Esc` exits.

**So the toolbar does not appear in your videos:** on KDE Plasma (KWin 6.4 or later) the toolbar is automatically excluded from recordings and streams: you see it, the video does not. **What you draw does appear in the video.** The same applies to the pop-up menus of the tray icon while you record. On other desktops there is no way to hide a window from the recording; the alternative is to record only a region and keep the toolbar outside it.

## Stream live

1. On the platform (YouTube, TikTok, Twitch…) get the **server address** and the **stream key**. TikTok requires you to meet its requirements to stream from a computer with a key.
2. **Directo** tab: paste both, choose 480p, 720p or 1080p and press *Transmitir en directo* (Stream live).
3. It streams screen + camera + audio (system and microphone) and saves a **local MP4 copy** in case the connection drops.
4. If the connection drops, it **reconnects by itself** (retries at 1, 2, 4, 8, 15 and 30 s); the window shows the status. If it never manages to connect (wrong address or key) it warns after 3 attempts.

**The key** is only saved if you tick "Recordar" (remember) (config file with 0600 permissions). It never appears in messages or in the log; the *Mostrar* (show) button reveals it and it hides again by itself.

While streaming there is no pause or zoom. Microphone noise reduction creates a virtual microphone "OweeCapture: micrófono sin ruido" (needs PipeWire with the echo-cancel module; if missing, the normal microphone is used and you are told). Test it before an important stream: how your voice sounds with the filter can only be judged by ear.

## Video tools

*Herramientas de vídeo* button in the window or the tray; it opens with your latest recording. **They always create a new file next to the original**, can be cancelled and never overwrite anything.

- **Trim** the start and the end, with thumbnails. In the preview, the *Aquí* (here) button sets the start or end where the video is and *▶ Ver el tramo* (watch the section) plays exactly what will remain.
- **Vertical 9:16** (1080×1920) for Shorts, TikTok and Reels: the whole video over a blurred background, or cropped choosing which part stays. Check each platform's duration limit.
- **Cut silences** (soft, normal or strong): ideal for tutorials.
- **Automatic subtitles**, local: create an `.srt` file next to the video (works on YouTube) and, if you want, burn them into the video TikTok-style.

They can be combined: trim → silences → subtitles → vertical.

### Subtitles: the download

The engine (faster-whisper, "base" model) **is not included**: it is downloaded if you accept, with a button in the tools. **It weighs about 620 MB** and is installed in `~/.local/share/oweecapture/`; remove it by deleting the `voz/` and `modelos/` folders there. Audio never leaves your computer. Quality with real speech must be judged by ear.

## Start with the desktop

Enable **Iniciar OweeCapture al abrir la sesión** (start OweeCapture when the session opens) (*Grabar* tab). It creates `~/.config/autostart/oweecapture.desktop`, which starts only the tray icon and shortcuts, without opening the window. To remove it, untick the box.

## Where everything is stored

| What | Where |
|---|---|
| Screenshots | `Pictures/Screenshots` |
| Recordings | `Videos/Screen Recordings/grabacion-….mp4` |
| Clips | `Videos/Screen Recordings/Clips` |
| Settings | `~/.config/oweecapture/config.json` |
| Remembered screen choice | `~/.config/oweecapture/portal.json` |
| Recording errors | `~/.cache/oweecapture/error.log` |
| Startup errors | `~/.cache/oweecapture/arranque.log` |
| Recording in progress (temporary) | `~/.cache/oweecapture/rec/` |
| Subtitle engine | `~/.local/share/oweecapture/` |
