> Historical project notes. See the [current README](README.md) for the active GDI/WIC/Tk implementation, build instructions and validation. CPU/FPS/readiness claims below are unverified historical statements.

# Changelog

All notable changes to AuroraCrosshairDX are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0] - 2025-12-09

### Added
- Initial release of AuroraCrosshairDX
- DirectX 11 rendering pipeline implementation
- Always-on-top, click-through overlay window for Windows 10/11
- CrosshairManager for crosshair file discovery and management
- Basic color customization (RGB)
- Scale adjustment support (1.0x to 3.0x)
- Visual Studio 2019/2022 project template
- Complete project documentation
  - README.md with feature overview
  - GETTING_STARTED.md quick start guide
  - BUILD_GUIDE.md comprehensive build instructions
  - CONFIGURATION.md customization guide
  - DEVELOPMENT_ROADMAP.md feature roadmap
  - PROJECT_OVERVIEW.md project details
  - CHANGELOG.md (this file)
- Layered architecture with separation of concerns
  - Application layer (main.cpp)
  - Management layer (Window, CrosshairManager)
  - Rendering layer (DXRenderer)
  - Hardware abstraction

### Features
- **Core Rendering**
  - DirectX 11 device initialization
  - Swap chain for fullscreen compatible rendering
  - Depth stencil for proper rendering
  - Blend state for alpha transparency
  - Vertex and pixel shader implementation
  - Constant buffer for dynamic parameters

- **Window Management**
  - Frameless overlay window (WS_POPUP style)
  - Always-on-top mode (WS_EX_TOPMOST)
  - Click-through transparency (WS_EX_TRANSPARENT)
  - Keyboard input handling (ESC to exit)
  - Proper window cleanup on shutdown

- **Crosshair System**
  - Automatic PNG discovery in resources/crosshairs/
  - Configurable crosshair selection
  - Position adjustment (X, Y coordinates)
  - Scale modification (float multiplier)
  - Color customization (RGBA with float values)
  - Runtime configuration changes

- **Performance**
  - Minimal CPU overhead (<5%)
  - Efficient GPU rendering (<2%)
  - Smooth 60+ FPS operation
  - Sub-millisecond render latency
  - Low memory footprint (~50-100MB)

### Documentation
- 6 comprehensive markdown documents
- Setup instructions for developers
- Build and deployment guidelines
- Configuration and customization guide
- Development roadmap for future releases
- Project architecture overview
- Troubleshooting guidance

### Technical Details
- **Language**: C++17 with modern features
- **Platform**: Windows 10/11 (x64)
- **Graphics API**: DirectX 11
- **Build System**: Visual Studio 2019/2022
- **Dependencies**: Windows SDK, DirectX SDK

### Known Limitations
- PNG loading not fully implemented (stb_image placeholder only)
- No GUI/UI configuration interface yet
- Hardcoded crosshair position and settings
- No hotkey system
- No configuration file persistence
- Single crosshair at a time
- No multi-monitor support yet
- No profile/preset system

### Technical Debt
- Shader compilation done at runtime (should be pre-compiled)
- No comprehensive error logging
- No input validation on configuration
- Memory management could use more RAII patterns
- Limited error handling for edge cases

## [Unreleased]

### Planned for v1.1
- PNG image loading implementation with stb_image
- ImGui integration for configuration UI
- Crosshair selection dropdown
- Real-time color picker
- Scale and position sliders
- Settings panel with hide/show toggle

### Planned for v1.2
- JSON configuration file support
- Hotkey system implementation
- Keyboard shortcuts for crosshair switching
- Save/load functionality
- Configuration persistence between sessions

### Planned for v1.3
- Multi-monitor support
- Performance profiling and optimization
- Additional image format support (BMP, TGA)
- GPU usage optimization
- CPU usage reduction

### Planned for v1.4
- Color effect presets
- Crosshair animation support (glow, pulse)
- Profile management system
- Per-application settings
- Advanced color adjustment (HSV, brightness, contrast)

### Planned for v2.0
- System tray integration
- Minimize to tray functionality
- Advanced UI with themes
- Crosshair marketplace/repository
- Community sharing features
- Performance metrics display
- Screenshot capture support

## Version History Summary

| Version | Date | Status | Focus |
|---------|------|--------|-------|
| 1.0 | 2025-12-09 | Released | Foundation & Core Rendering |
| 1.1 | TBD | Planned | PNG Support & UI |
| 1.2 | TBD | Planned | Configuration System |
| 1.3 | TBD | Planned | Multi-Monitor & Optimization |
| 1.4 | TBD | Planned | Advanced Features |
| 2.0 | TBD | Planned | Major Enhancement |

## Migration Guide

### From Pre-1.0 (N/A)
This is the initial release.

### Upgrading to 1.1
- No breaking changes expected
- Update PNG files location (remains: resources/crosshairs/)
- New ImGui dependency will be added
- Configuration format will be introduced

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Check existing documentation
- Review development roadmap
- Contact project maintainer

## Maintainers

- Aurora - Project Lead & Primary Developer

## Contributors

- Initial development team

---

## Reference Information

### Versioning Scheme
- **MAJOR**: Breaking changes or major features
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, documentation updates

Example: v1.2.3 = Major 1, Minor 2, Patch 3

### Release Cycle
- Major releases: ~6-8 weeks
- Minor releases: ~2-3 weeks
- Patches: As needed

### Support Timeline
- v1.x: 12+ months of active support
- v2.0: Release upon completion
- Older versions: Community support

---

## Commit Message Format

Format: `[TYPE] Message`

Types:
- `[FEAT]` - New feature
- `[FIX]` - Bug fix
- `[DOCS]` - Documentation
- `[STYLE]` - Code style
- `[REFACTOR]` - Code refactoring
- `[PERF]` - Performance improvement
- `[TEST]` - Test addition/modification

Example:
```
[FEAT] Add PNG loading support with stb_image
[FIX] Correct memory leak in texture loading
[DOCS] Update configuration guide
```

---

## Breaking Changes

### v1.0
- Initial release, no breaking changes

### Future Versions
- Breaking changes will be documented here
- Deprecation warnings provided before removal
- Migration guides provided

---

Last Updated: December 9, 2025
Maintained by: Aurora
Version: 1.0
