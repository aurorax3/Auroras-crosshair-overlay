# Aurora Crosshair Overlay

A lightweight, always-on-top transparent gaming crosshair overlay for Windows with customizable PNG crosshairs and real-time GUI control.

## Features

✅ **Transparent Overlay** - True transparency with custom crosshair textures  
✅ **Live Scale Control** - Adjust crosshair size from 50% to 300%  
✅ **Crosshair Selection** - Choose between multiple PNG crosshairs  
✅ **Dynamic Resolution** - Automatically detects your monitor size  
✅ **GUI Controller** - Easy-to-use interface to manage settings  
✅ **Click-Through** - Overlay doesn't interfere with mouse/keyboard  
✅ **Always-On-Top** - Stays above all other windows (except exclusive fullscreen)  
✅ **Config-Based** - Settings persist and update in real-time  

## Installation

### Requirements
- Windows 10/11 (64-bit)
- Python 3.6+ (for GUI only, overlay runs standalone)

### Setup

1. **Clone or download** the project to your Documents folder:
   ```
   C:\Users\YourName\Documents\Crosshair overlay\
   ```

2. **Install Python dependencies** (for GUI):
   ```powershell
   python -m pip install psutil
   ```
   If psuitl doesn't install pillow automatically run:
    ```powershell
    pip install pillow
    ```

4. **Done!** The overlay executable is pre-built at:
   ```
   x64\Release\AuroraCrosshairDX.exe
   ```

## Usage

### Starting the Overlay

**Option 1: GUI Controller (Recommended)**
```bash
cd CrosshairGUI
python gui.py
```

This opens a GUI where you can:
- Select crosshair images
- Adjust scale with a slider (50%-300%)
- Start/stop overlay
- Monitor status

**Option 2: Direct Execution**
```bash
x64\Release\AuroraCrosshairDX.exe
```

This runs the overlay with default settings (osupink.png at 100% scale).

### Controlling Settings

Settings are stored in `overlay_config.txt`:
```
scale=1.5
crosshair=osupink.png
```

The overlay checks for config updates every 500ms, so changes apply instantly!

#### Scale Values
- `0.5` = 50% (small crosshair)
- `1.0` = 100% (default size)
- `1.5` = 150% (medium)
- `2.0` = 200% (large)
- `3.0` = 300% (maximum)

#### Available Crosshairs
Place PNG images in `resources\crosshairs\`:
- `osupink.png` (default)
- `gaypink.png`
- `prodg_diamond_quartered.png`
- (Add more PNG files here)

## GUI Controls

### Crosshair Selection
Select from all available PNG files in the resources folder.

### Scale Slider
Drag to adjust crosshair size from 50% to 300%. Changes apply instantly!

### Status Display
Shows whether overlay is running and any errors.

### Start/Stop Buttons
- **Start Overlay** - Launches the overlay process
- **Stop Overlay** - Cleanly closes the overlay
- **Refresh Status** - Updates status indicator

## Limitations

### Exclusive Fullscreen (True Fullscreen)
⚠️ **Does not work** on exclusive fullscreen due to Windows architecture:
- Use **Borderless Windowed** mode instead (minimal performance impact)
- Most modern games support this mode
- No difference to gamers - same visual quality, slightly better overlay support

### Supported Modes
✅ Windowed (resizable)  
✅ Borderless Windowed  
⚠️ Exclusive Fullscreen (not supported by design)  

## Performance

- ~60 FPS overlay rendering
- Minimal CPU usage (<1%)
- Negligible memory footprint
- Click-through reduces input latency

## Troubleshooting

### GUI doesn't start
```powershell
python -m pip install psutil
```

### Overlay not showing
1. Check if game is in borderless windowed mode (not exclusive fullscreen)
2. Try restarting the overlay
3. Verify `osupink.png` exists in `resources\crosshairs\`

### Settings not updating
- Config file syntax must be exact: `scale=1.0` (use period for decimals)
- Overlay checks for changes every 500ms
- Close and restart GUI if stuck

### Crosshairs not loading
1. Check PNG format is valid (try opening in Paint)
2. Verify file is in `resources\crosshairs\` folder
3. Ensure filename in config exactly matches filename (case-sensitive)

## Configuration Files

```
Documents\Crosshair overlay\
├── AuroraCrosshairDX\              (Overlay executable & code)
│   ├── x64\Release\
│   │   └── AuroraCrosshairDX.exe
│   └── resources\crosshairs\
│       ├── osupink.png
│       ├── gaypink.png
│       └── prodg_diamond_quartered.png
├── CrosshairGUI\                   (GUI Controller)
│   ├── gui.py
│   └── run_gui.bat
└── overlay_config.txt              (Runtime config)
```

## Customization

### Adding New Crosshairs
1. Place PNG file in `resources\crosshairs\`
2. Restart GUI or manually update `overlay_config.txt`
3. Select from dropdown in GUI

### Changing Default Crosshair
Edit the overlay code in `src\main.cpp`:
```cpp
wchar_t g_crosshairName[256] = L"osupink.png";  // Change this line
```

### Changing Default Scale
Edit overlay code:
```cpp
float g_scale = 1.0f;  // Change to 1.5, 2.0, etc.
```

## Advanced: Building from Source

### Build Overlay
```bash
cd AuroraCrosshairDX
msbuild AuroraCrosshairDX.sln /p:Configuration=Release /p:Platform=x64
```

Requires:
- Visual Studio 2022 (BuildTools)
- Windows SDK
- C++17 support

## FAQ

**Q: Can I use this on exclusive fullscreen games?**  
A: No - Windows prevents this by design. Use borderless windowed mode instead.

**Q: Does this work with competitive games?**  
A: Yes - it's a transparent overlay with no game modification. Some anti-cheats might still detect it. Use at your own risk.

**Q: Can I make custom crosshairs?**  
A: Yes! Create a PNG image with transparency. Transparent areas won't show.

**Q: Will this get me banned?**  
A: It's just an overlay - same as Discord overlay. However, competitive games with strict anti-cheats may flag it. Always check your game's terms.

**Q: How do I uninstall?**  
A: Just delete the folder. No registry entries or system modifications.

## License

This project is provided as-is for personal use.

## Support

Having issues? Try:
1. Restart overlay: Stop → Start
2. Verify config file syntax
3. Check PNG crosshair files exist
4. Make sure game is in borderless windowed mode

---

**Enjoy your new crosshair overlay!** 🎮
