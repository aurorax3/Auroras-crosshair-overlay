> Historical project notes. See the [current README](../README.md) for the active GDI/WIC/Tk implementation, build instructions and validation. CPU/FPS/readiness claims below are unverified historical statements.

# AuroraCrosshairDX

A DirectX 11 crosshair overlay for Windows (fullscreen compatible).

## Features
- **Always-on-top, click-through overlay**: Window stays on top and transparent to clicks
- **Per-pixel alpha PNG crosshair rendering**: Load PNG files with per-pixel transparency
- **Crosshair selection from `resources/crosshairs/`**: Automatically discovers PNG crosshairs
- **Scale and color customization**: Runtime adjustable scale and RGB color
- **Visual Studio project template**: Ready-to-build solution

## Project Structure

```
AuroraCrosshairDX/
├── include/
│   ├── DXRenderer.h          # DirectX 11 rendering engine
│   ├── Window.h              # Windows window management
│   ├── CrosshairManager.h    # Crosshair selection & config
│   └── stb_image.h           # PNG loading (placeholder)
├── src/
│   ├── main.cpp              # Application entry point
│   ├── DXRenderer.cpp        # DirectX implementation
│   ├── Window.cpp            # Window implementation
│   └── CrosshairManager.cpp  # Crosshair manager implementation
├── resources/
│   └── crosshairs/           # Place PNG crosshair files here
├── AuroraCrosshairDX.vcxproj # Visual Studio project file
└── README.md                 # This file
```

## Setup Instructions

### Prerequisites
- Visual Studio 2019 or 2022 (C++ workload)
- Windows 10/11 SDK
- DirectX 11 SDK (usually included with Windows SDK)

### Build Steps

1. **Clone/Open the project**:
   ```
   Open AuroraCrosshairDX.sln in Visual Studio
   ```

2. **Add PNG Crosshairs**:
   - Create PNG image files for your crosshairs (transparent background, white/colored crosshair)
   - Place them in `resources/crosshairs/`
   - Example: `resources/crosshairs/default.png`

3. **Configure stb_image** (for PNG loading):
   - Download `stb_image.h` from: https://github.com/nothings/stb/blob/master/stb_image.h
   - Replace `include/stb_image.h` with the downloaded file
   - In one of your source files, add:
     ```cpp
     #define STB_IMAGE_IMPLEMENTATION
     #include "stb_image.h"
     ```

4. **Build**:
   - Select `Release | x64` configuration
   - Build the solution (Ctrl+Shift+B)

5. **Run**:
   - The executable will appear in `x64/Release/`
   - Press ESC to exit the application

## Configuration

### Modify Crosshair in Runtime
Edit `src/main.cpp` to customize:
- Crosshair path
- Initial position
- Scale
- Color (RGBA)

Example:
```cpp
crosshairManager.SetPosition(960, 540);    // Center screen
crosshairManager.SetScale(2.0f);           // 2x scale
crosshairManager.SetColor(0.0f, 1.0f, 0.0f, 1.0f);  // Green
```

## Dependencies

### Required
- **DirectX 11 SDK** - For rendering
- **d3d11.lib**, **dxgi.lib**, **d3dcompiler.lib** - DirectX libraries
- **windowscodecs.lib** - Windows imaging support

### Optional
- **stb_image.h** - For PNG file loading (currently not fully implemented)
- **ImGui** - For UI (future enhancement)

## TODO / Future Enhancements

- [ ] Implement PNG loading with stb_image
- [ ] Add ImGui for real-time UI configuration
  - Crosshair selection dropdown
  - Scale slider
  - Color picker
  - Position adjustment
- [ ] Load configuration from JSON/INI file
- [ ] Support for other image formats (BMP, TGA)
- [ ] Hotkey system for quick customization
- [ ] Multi-monitor support
- [ ] Performance optimization for overlay mode

## Troubleshooting

### Window not appearing
- Ensure DirectX 11 is properly installed
- Check that `window.Create()` is called with valid parameters
- Verify GPU supports DirectX 11

### Crosshair not rendering
- Ensure PNG file is in `resources/crosshairs/`
- Verify PNG has alpha channel (transparency)
- Check file path in `main.cpp`

### Build errors
- Update Visual Studio to latest version
- Install DirectX SDK if missing
- Ensure C++17 standard is selected

## License

This project is provided as-is for educational and personal use.

## References

- [DirectX 11 Documentation](https://docs.microsoft.com/en-us/windows/win32/direct3d11/atoc-dx-graphics-direct3d-11)
- [stb_image](https://github.com/nothings/stb)
- [ImGui](https://github.com/ocornut/imgui) (for future UI implementation)
