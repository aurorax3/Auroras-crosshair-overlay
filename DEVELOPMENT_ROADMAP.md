> Historical project notes. See the [current README](README.md) for the active GDI/WIC/Tk implementation, build instructions and validation. CPU/FPS/readiness claims below are unverified historical statements.

# Development Roadmap

## Current Status: v1.0 Foundation

**Core Features Implemented:**
- ✅ DirectX 11 rendering pipeline
- ✅ Always-on-top overlay window (transparent to clicks)
- ✅ Crosshair texture loading framework
- ✅ Basic color and scale customization
- ✅ Visual Studio project template

**Known Limitations:**
- PNG loading not yet implemented (stb_image placeholder)
- No UI/configuration interface
- Hardcoded position and settings
- No hotkey support
- No configuration file support

---

## v1.1: PNG Support & Basic UI

### PNG Image Loading
- [ ] Implement stb_image integration
  - Download and integrate actual stb_image.h
  - Create PNG loader utility class
  - Handle image format validation
  - Error handling for corrupted files
- [ ] Test with various PNG formats
  - PNG-32 (with alpha)
  - Different compression levels
  - Various dimensions

### ImGui Integration
- [ ] Add ImGui dependency
- [ ] Create configuration panel
  - Crosshair selection dropdown
  - Scale slider (0.5x - 3.0x)
  - RGB color picker
  - Position adjusters (X, Y)
- [ ] Add hide/show toggle (key: Tab)
- [ ] Save/load settings to JSON

**Estimated**: 2-3 weeks

---

## v1.2: Configuration System

### JSON Configuration File
- [ ] Create config file format
```json
{
  "crosshair": "default.png",
  "position": { "x": 960, "y": 540 },
  "scale": 1.0,
  "color": { "r": 0.0, "g": 1.0, "b": 0.0, "a": 1.0 },
  "opacity": 1.0,
  "hotkeys": {
    "toggle": "Tab",
    "cycleNext": "Right",
    "cyclePrev": "Left"
  }
}
```
- [ ] Implement config loader/saver
- [ ] Add config validation
- [ ] Auto-load on startup

### Hotkey System
- [ ] Register global hotkeys
  - Toggle visibility (Tab)
  - Cycle to next crosshair (Right Arrow)
  - Cycle to previous crosshair (Left Arrow)
  - Increase scale (Up Arrow)
  - Decrease scale (Down Arrow)
- [ ] Conflict detection
- [ ] Customizable hotkeys via config

**Estimated**: 2 weeks

---

## v1.3: Enhanced Features

### Multi-Monitor Support
- [ ] Detect all monitors
- [ ] Allow selection of target monitor
- [ ] Adjust window size per monitor
- [ ] Handle monitor hotplug events

### Additional Image Formats
- [ ] BMP support
- [ ] TGA support
- [ ] JPEG support (with fallback)

### Performance Optimization
- [ ] Profile rendering pipeline
- [ ] Optimize constant buffer updates
- [ ] Implement render target caching
- [ ] Add performance metrics display

**Estimated**: 3 weeks

---

## v1.4: Advanced Customization

### Color Management
- [ ] Color presets (Red, Green, Blue, Custom)
- [ ] Color history/favorites
- [ ] HSV color picker alternative
- [ ] Brightness/Contrast adjustment

### Crosshair Effects
- [ ] Glow effect (shader-based)
- [ ] Pulsing animation
- [ ] Rotation animation
- [ ] Multiple layer support

### Profile System
- [ ] Save multiple profiles
- [ ] Quick-switch between profiles
- [ ] Per-application profiles
  - Auto-detect active window
  - Load settings automatically

**Estimated**: 4 weeks

---

## v2.0: Major Enhancements

### Advanced UI
- [ ] Skin/theme system
- [ ] Tray icon with menu
- [ ] Minimize to system tray
- [ ] Settings dialog

### Recording & Streaming
- [ ] Overlay statistics display
  - FPS counter
  - Frame time
  - GPU usage
- [ ] Screenshot capture (Printscreen)
- [ ] Replay system integration (OBS, NVIDIA)

### Marketplace
- [ ] Community crosshair repository
- [ ] Download crosshairs in-app
- [ ] Rating system
- [ ] Share custom crosshairs

**Estimated**: 6-8 weeks

---

## v2.1+: Future Possibilities

### Machine Learning
- [ ] Aim assist (configurable, ethical)
- [ ] Crosshair suggestion based on game
- [ ] Sensitivity converter

### Integration
- [ ] Game-specific profiles
- [ ] Discord Rich Presence
- [ ] Streaming platform integration
- [ ] Accessibility features

### Community
- [ ] Contributor guidelines
- [ ] Plugin system
- [ ] Open source contributions

---

## Implementation Priority

### Must Have (MVP)
1. PNG loading ✅ (v1.1)
2. ImGui UI ✅ (v1.1)
3. Configuration file ✅ (v1.2)
4. Hotkey system ✅ (v1.2)

### Should Have
5. Multi-monitor support (v1.3)
6. Performance optimization (v1.3)
7. Color presets (v1.4)
8. Profile system (v1.4)

### Nice to Have
9. Advanced effects (v1.4)
10. Tray integration (v2.0)
11. Crosshair marketplace (v2.0)

---

## Technical Debt

### Current Issues
- [ ] Shader compilation done at runtime (optimize)
- [ ] No error logging system
- [ ] No input validation on config loading
- [ ] Memory management could be improved

### Refactoring Needed
- [ ] Separate shader code into .hlsl files
- [ ] Create logging utility
- [ ] Add configuration validator
- [ ] Implement RAII patterns more thoroughly
- [ ] Add comprehensive error handling

---

## Testing Strategy

### Unit Tests
- [ ] Config file parsing
- [ ] File discovery (crosshairs)
- [ ] Color validation
- [ ] Position clamping

### Integration Tests
- [ ] PNG loading workflow
- [ ] DirectX initialization
- [ ] Hotkey registration
- [ ] Config save/load cycle

### Performance Tests
- [ ] Memory leak detection
- [ ] CPU/GPU profiling
- [ ] Frame time consistency
- [ ] Stress testing (many crosshairs)

---

## Community Contribution

### How to Contribute
1. Fork the repository
2. Create feature branch: `git checkout -b feature/png-loading`
3. Implement feature with tests
4. Submit pull request with description

### Contribution Areas
- [ ] PNG loader implementation
- [ ] ImGui UI components
- [ ] Documentation improvements
- [ ] Test coverage
- [ ] Performance optimizations
- [ ] Bug fixes

---

## Version History

### v1.0 (Current)
- Initial release
- Core rendering pipeline
- Basic customization

### Planned Releases
- v1.1: PNG Support
- v1.2: Configuration System
- v1.3: Multi-Monitor & Optimization
- v1.4: Advanced Features
- v2.0: Major Enhancements

---

## Resources & References

### Libraries to Integrate
- [stb_image](https://github.com/nothings/stb/blob/master/stb_image.h) - Image loading
- [ImGui](https://github.com/ocornut/imgui) - UI framework
- [nlohmann/json](https://github.com/nlohmann/json) - JSON parsing
- [spdlog](https://github.com/gabime/spdlog) - Logging

### Learning Resources
- [DirectX 11 Tutorial](https://www.directxtutorial.com/)
- [ImGui Documentation](https://github.com/ocornut/imgui/wiki)
- [Game Development Patterns](https://gameprogrammingpatterns.com/)

### Similar Projects
- [Crosshair V2](https://github.com/)
- [Overlay Framework](https://github.com/)
- [Game Utilities](https://github.com/)

---

*Last Updated: December 2025*
*Maintainer: Aurora*
