> Historical project notes. See the [current README](README.md) for the active GDI/WIC/Tk implementation, build instructions and validation. CPU/FPS/readiness claims below are unverified historical statements.

# Quick Reference Card

## File Locations
```
📁 Crosshair overlay/
   📄 START_HERE.md                  👈 Read this first!
   📄 GETTING_STARTED.md
   📄 BUILD_GUIDE.md
   📄 CONFIGURATION.md
   📄 PROJECT_OVERVIEW.md
   📄 DEVELOPMENT_ROADMAP.md
   📄 CHANGELOG.md
   📁 AuroraCrosshairDX/
      📄 AuroraCrosshairDX.vcxproj   👈 Open this in VS
      📄 README.md
      📁 include/
         📄 DXRenderer.h
         📄 Window.h
         📄 CrosshairManager.h
         📄 stb_image.h
      📁 src/
         📄 main.cpp
         📄 DXRenderer.cpp
         📄 Window.cpp
         📄 CrosshairManager.cpp
      📁 resources/
         📁 crosshairs/             👈 Place PNG files here
   📄 AuroraCrosshairDX.sln          👈 Open in Visual Studio
```

## Quick Commands

### Visual Studio
| Action | Shortcut |
|--------|----------|
| Open Solution | Ctrl+O → Select .sln |
| Build Project | Ctrl+Shift+B |
| Run (Debug) | F5 |
| Run (No Debug) | Ctrl+F5 |
| Stop Execution | Shift+F5 |
| Clean Solution | Build → Clean Solution |
| Rebuild Solution | Build → Rebuild Solution |
| Open Output Window | View → Output |
| Performance Profiler | Debug → Performance Profiler |

### Common Tasks
| Task | Steps |
|------|-------|
| Change crosshair color | Edit `main.cpp` → `SetColor()` → Rebuild |
| Change crosshair size | Edit `main.cpp` → `SetScale()` → Rebuild |
| Move crosshair | Edit `main.cpp` → `SetPosition()` → Rebuild |
| Add crosshair PNG | Place in `resources/crosshairs/` |
| Exit application | Press ESC key |

## Code Snippets

### Change Color to Green
```cpp
// In main.cpp, inside wWinMain()
crosshairManager.SetColor(0.0f, 1.0f, 0.0f, 1.0f);
```

### Change Size to 1.5x
```cpp
// In main.cpp, inside wWinMain()
crosshairManager.SetScale(1.5f);
```

### Center Crosshair
```cpp
// In main.cpp, inside wWinMain()
crosshairManager.SetPosition(960, 540);  // For 1920x1080
```

### Load Different Crosshair
```cpp
// In main.cpp, inside wWinMain()
crosshairManager.SelectCrosshair(1);  // Index 1 (second file)
```

## Color Values (RGBA Format)

### Basic Colors
```
Red       (1.0, 0.0, 0.0, 1.0)
Green     (0.0, 1.0, 0.0, 1.0)
Blue      (0.0, 0.0, 1.0, 1.0)
White     (1.0, 1.0, 1.0, 1.0)
Black     (0.0, 0.0, 0.0, 1.0)
Yellow    (1.0, 1.0, 0.0, 1.0)
Cyan      (0.0, 1.0, 1.0, 1.0)
Magenta   (1.0, 0.0, 1.0, 1.0)
```

### Transparency Examples
```
Opaque (100%)     → Alpha = 1.0
75% Visible       → Alpha = 0.75
50% Visible       → Alpha = 0.5
25% Visible       → Alpha = 0.25
Invisible (0%)    → Alpha = 0.0
```

## Display Resolutions

| Resolution | Width | Height | Center X | Center Y |
|-----------|-------|--------|----------|----------|
| 1080p | 1920 | 1080 | 960 | 540 |
| 1440p | 2560 | 1440 | 1280 | 720 |
| 4K | 3840 | 2160 | 1920 | 1080 |
| 720p | 1280 | 720 | 640 | 360 |

## System Requirements

✅ **Minimum**
- Windows 10/11 (64-bit)
- Intel Core i5
- 2 GB RAM
- DirectX 11 GPU

✅ **Recommended**
- Windows 11 (64-bit)
- Intel Core i7+
- 8 GB RAM
- Modern GPU (GTX 1060+)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ESC | Exit Application |
| Ctrl+Shift+B | Build (VS) |
| F5 | Debug (VS) |
| Ctrl+F5 | Run without Debug (VS) |

## Project Structure Overview

```
┌─────────────────────────────┐
│   Application (main.cpp)    │
└────────────┬────────────────┘
             │
     ┌───────┼───────┐
     │       │       │
     ▼       ▼       ▼
┌────────┬──────────┬──────────────┐
│ Window │ Renderer │ Crosshair    │
│Manager │          │ Manager      │
└────────┴──────────┴──────────────┘
     │       │       │
     │       ▼       │
     │   ┌───────┐   │
     └──▶│ GPU   │◀──┘
         └───────┘
```

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Won't build | Install Windows SDK |
| Can't find d3d11.lib | Check VC++ library paths |
| Application crashes | Update GPU driver |
| Window is blank | Rebuild shaders |
| Crosshair invisible | Check PNG file location |
| Overlay goes behind | Window is not top-most |

## Important Files

| File | Purpose | Edit? |
|------|---------|-------|
| main.cpp | Entry point, settings | ✅ Yes |
| DXRenderer.cpp | Rendering code | ⚠️ Advanced |
| Window.cpp | Window code | ⚠️ Advanced |
| CrosshairManager.cpp | File discovery | ⚠️ Advanced |
| .vcxproj | Project config | ❌ No |

## Memory/Performance Budget

| Metric | Target | Acceptable |
|--------|--------|-----------|
| Memory | <100 MB | <150 MB |
| CPU | <3% | <5% |
| GPU | <1% | <2% |
| FPS | 60+ | 30+ |
| Latency | <1ms | <5ms |

## Git Workflow

```bash
# Clone
git clone <repo-url>

# Create branch
git checkout -b feature/my-feature

# Make changes
git add .
git commit -m "[FEAT] Description"

# Push
git push origin feature/my-feature

# Create PR on GitHub
```

## File Extensions

| Extension | Type | Location |
|-----------|------|----------|
| .cpp | Source Code | src/ |
| .h | Header File | include/ |
| .vcxproj | Project File | Root |
| .sln | Solution File | Root |
| .png | Crosshair Image | resources/crosshairs/ |
| .md | Documentation | Root |

## Shader Compilation

Shaders are compiled at runtime in DXRenderer.cpp:
- Vertex shader: `vertexShaderSource`
- Pixel shader: `pixelShaderSource`

To optimize, compile to .cso files (advanced).

## Future Enhancements

| Feature | Version | Status |
|---------|---------|--------|
| PNG Loading | 1.1 | Planned |
| ImGui UI | 1.1 | Planned |
| Hotkeys | 1.2 | Planned |
| Multi-Monitor | 1.3 | Planned |
| Effects | 1.4 | Planned |
| Marketplace | 2.0 | Planned |

## Support

- 📖 **Docs**: See documentation files
- 🐛 **Bugs**: Check BUILD_GUIDE.md troubleshooting
- 🤔 **Questions**: Review PROJECT_OVERVIEW.md
- 🛠️ **Development**: See DEVELOPMENT_ROADMAP.md

## Version Info

- **Current Version**: 1.0
- **Release Date**: December 9, 2025
- **Status**: Complete & Ready
- **Maintenance**: Active

## Quick Links

| Link | Purpose |
|------|---------|
| START_HERE.md | Begin here |
| GETTING_STARTED.md | Quick setup |
| BUILD_GUIDE.md | Detailed build |
| CONFIGURATION.md | Customization |
| PROJECT_OVERVIEW.md | Architecture |
| DEVELOPMENT_ROADMAP.md | Future plans |

---

**Print this card for quick reference!** 🎯

*Last Updated: December 9, 2025*
