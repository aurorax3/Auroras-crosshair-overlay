> Historical project notes. See the [current README](README.md) for the active GDI/WIC/Tk implementation, build instructions and validation. CPU/FPS/readiness claims below are unverified historical statements.

# Getting Started

## Quick Start Guide

### 1. Visual Studio Setup
1. Open `AuroraCrosshairDX.sln` in Visual Studio
2. Select `Release | x64` configuration from the top toolbar
3. Build the solution (Ctrl+Shift+B or Build > Build Solution)

### 2. Add Your Crosshair Images
1. Create or find PNG crosshair images
2. Place them in the `resources/crosshairs/` folder
3. Ensure PNGs have transparency (RGBA format)

### 3. Enable PNG Loading
1. Download `stb_image.h` from: https://github.com/nothings/stb/blob/master/stb_image.h
2. Replace `include/stb_image.h` with the downloaded file
3. Add this to one source file (e.g., top of `main.cpp`):
   ```cpp
   #define STB_IMAGE_IMPLEMENTATION
   #include "stb_image.h"
   ```

### 4. Run the Application
1. Build the project
2. Run the executable from `x64/Release/AuroraCrosshairDX.exe`
3. Press ESC to exit

## File Descriptions

### Headers (`include/`)
- **DXRenderer.h** - DirectX 11 rendering backend
- **Window.h** - Windows window creation and message handling
- **CrosshairManager.h** - Crosshair file discovery and configuration
- **stb_image.h** - PNG image loading library (placeholder)

### Source Files (`src/`)
- **main.cpp** - Application entry point
- **DXRenderer.cpp** - DirectX implementation
- **Window.cpp** - Windows API wrapper
- **CrosshairManager.cpp** - Crosshair manager implementation

## Key Functions

### DXRenderer
```cpp
bool Initialize(HWND hWnd);           // Initialize DirectX device
bool LoadPNGTexture(const wchar_t*);   // Load PNG crosshair
void RenderCrosshair(...);             // Render crosshair on screen
void Present();                        // Submit frame to display
```

### Window
```cpp
bool Create(const std::wstring&, unsigned int, unsigned int);  // Create overlay window
bool ProcessMessages();                // Handle Windows messages
```

### CrosshairManager
```cpp
bool LoadCrosshairsFromDirectory(const std::wstring&);  // Scan for PNGs
bool SelectCrosshair(size_t);          // Select crosshair by index
void SetScale(float);                  // Set crosshair scale
void SetColor(float, float, float);    // Set RGB color
void SetPosition(int, int);            // Set crosshair position
```

## Next Steps

1. **Customize the overlay**: Edit `main.cpp` to adjust initial settings
2. **Add UI**: Integrate ImGui for runtime configuration
3. **Add hotkeys**: Implement keyboard shortcuts for quick customization
4. **Load from config**: Add JSON/INI file support for saved configurations

## Support

For issues:
- Check the README.md for troubleshooting
- Verify all DirectX dependencies are installed
- Ensure PNG files are properly formatted with alpha channel
