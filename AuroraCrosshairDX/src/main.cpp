#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <wincodec.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <cstdint>
#include <limits>
#include <new>
#include <filesystem>
#include <wrl/client.h>
#include "OverlayLogic.h"

#ifdef _MSC_VER
#pragma comment(lib, "windowscodecs.lib")
#endif

HWND g_hWnd = nullptr;
int g_crosshairSize = 20;
int g_crosshairThickness = 3;
int g_screenWidth = 0;
int g_screenHeight = 0;
int g_screenLeft = 0, g_screenTop = 0;
std::vector<std::uint32_t> g_crosshairPixels;
std::uint64_t g_imageRevision = 0;
Microsoft::WRL::ComPtr<IWICImagingFactory> g_wicFactory;
int g_textureWidth = 0;
int g_textureHeight = 0;
float g_scale = 1.0f;  // Scale multiplier (1.0 = 100%)
std::wstring g_crosshairName = L"dots/osupink.png";
aurora::Settings g_settings;
std::filesystem::path g_resourceDirectory;
bool g_textureLoaded = false;  // Track if texture successfully loaded
bool g_useFallback = false;  // Force use fallback pink crosshair
bool g_redrawRequested = true;
std::wstring g_configDirectory;
std::wstring g_configPath;
std::wstring g_configParentDirectory;

std::wstring EnvironmentValue(const wchar_t* name)
{
    DWORD length = GetEnvironmentVariableW(name, nullptr, 0);
    if (!length) return {};
    std::wstring value(length, L'\0');
    DWORD written = GetEnvironmentVariableW(name, value.data(), length);
    if (!written || written >= length) return {};
    value.resize(written);
    return value;
}

std::wstring NativePath(const std::filesystem::path& path)
{
    auto value = path.lexically_normal().wstring();
    std::replace(value.begin(), value.end(), L'/', L'\\');
    if (value.size() >= MAX_PATH && value.rfind(L"\\\\?\\", 0) != 0)
    {
        if (value.rfind(L"\\\\", 0) == 0) value = L"\\\\?\\UNC\\" + value.substr(2);
        else if (path.is_absolute()) value = L"\\\\?\\" + value;
    }
    return value;
}

void EnablePhysicalPixelCoordinates()
{
    using SetContext = BOOL(WINAPI*)(DPI_AWARENESS_CONTEXT);
    auto setContext = reinterpret_cast<SetContext>(GetProcAddress(GetModuleHandleW(L"user32.dll"),
        "SetProcessDpiAwarenessContext"));
    if (!setContext || !setContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        SetProcessDPIAware(); // Older supported Windows installations.
}

void RefreshMonitorGeometry()
{
    // Preserve primary-monitor targeting; secondary monitors may have negative origins.
    POINT origin{};
    MONITORINFO monitor{};
    monitor.cbSize = sizeof(monitor);
    if (GetMonitorInfoW(MonitorFromPoint(origin, MONITOR_DEFAULTTOPRIMARY), &monitor))
    {
        g_screenLeft = monitor.rcMonitor.left;
        g_screenTop = monitor.rcMonitor.top;
        g_screenWidth = monitor.rcMonitor.right - monitor.rcMonitor.left;
        g_screenHeight = monitor.rcMonitor.bottom - monitor.rcMonitor.top;
    }
    else
    {
        g_screenLeft = g_screenTop = 0;
        g_screenWidth = GetSystemMetrics(SM_CXSCREEN);
        g_screenHeight = GetSystemMetrics(SM_CYSCREEN);
    }
    g_redrawRequested = true;
}

std::filesystem::path FindResources()
{
    // Match the Python controller: explicit/legacy home assets take precedence
    // even when its executable falls back to a checkout build.
    auto homeResources = std::filesystem::path(g_configDirectory) /
        L"AuroraCrosshairDX" / L"resources" / L"crosshairs";
    std::error_code resourceError;
    if (std::filesystem::is_directory(homeResources, resourceError)) return homeResources;
    std::wstring executable(512, L'\0');
    for (;;)
    {
        DWORD length = GetModuleFileNameW(nullptr, executable.data(), static_cast<DWORD>(executable.size()));
        if (!length) break;
        if (length < executable.size())
        {
            executable.resize(length);
            auto directory = std::filesystem::path(executable).parent_path();
            for (int depth = 0; depth < 8 && !directory.empty(); ++depth)
            {
                for (const auto& candidate : {directory / L"resources" / L"crosshairs",
                    directory / L"AuroraCrosshairDX" / L"resources" / L"crosshairs"})
                {
                    std::error_code error;
                    if (std::filesystem::is_directory(candidate, error)) return candidate;
                }
                auto parent = directory.parent_path();
                if (parent == directory) break;
                directory = parent;
            }
            break;
        }
        if (executable.size() >= 32768) break;
        executable.resize(executable.size() * 2);
    }
    return homeResources;
}

std::wstring SelectedTexturePath()
{
    return NativePath(g_resourceDirectory / std::filesystem::path(g_crosshairName));
}

struct ConfigStamp
{
    bool exists = false;
    FILETIME modified{};
    DWORD sizeHigh = 0, sizeLow = 0;
};

bool ConfigurationChanged(ConfigStamp& previous)
{
    WIN32_FILE_ATTRIBUTE_DATA info{};
    ConfigStamp current;
    current.exists = GetFileAttributesExW(NativePath(g_configPath).c_str(), GetFileExInfoStandard, &info) != FALSE;
    if (current.exists)
    {
        current.modified = info.ftLastWriteTime;
        current.sizeHigh = info.nFileSizeHigh;
        current.sizeLow = info.nFileSizeLow;
    }
    bool changed = current.exists != previous.exists ||
        CompareFileTime(&current.modified, &previous.modified) != 0 ||
        current.sizeHigh != previous.sizeHigh || current.sizeLow != previous.sizeLow;
    previous = current;
    return changed;
}

HANDLE WatchConfigurationDirectory()
{
    return FindFirstChangeNotificationW(NativePath(g_configDirectory).c_str(), FALSE,
        FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_LAST_WRITE | FILE_NOTIFY_CHANGE_SIZE);
}

HANDLE WatchConfigurationParent()
{
    if (g_configParentDirectory.empty()) return INVALID_HANDLE_VALUE;
    return FindFirstChangeNotificationW(NativePath(g_configParentDirectory).c_str(),
        FALSE, FILE_NOTIFY_CHANGE_DIR_NAME);
}

void CloseDirectoryWatch(HANDLE& watch)
{
    if (watch != INVALID_HANDLE_VALUE) FindCloseChangeNotification(watch);
    watch = INVALID_HANDLE_VALUE;
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    switch (message)
    {
    case WM_CLOSE:
        DestroyWindow(hWnd);
        return 0;
    case WM_DISPLAYCHANGE:
    case WM_DPICHANGED:
    case WM_SETTINGCHANGE:
        // The suggested DPI rectangle describes a conventional window; this one
        // stays physically centered with its own crosshair-sized bitmap.
        RefreshMonitorGeometry();
        return 0;
    case WM_DWMCOMPOSITIONCHANGED:
        g_redrawRequested = true;
        return 0;
    case WM_POWERBROADCAST:
        if (wParam == PBT_APMRESUMEAUTOMATIC || wParam == PBT_APMRESUMESUSPEND)
            RefreshMonitorGeometry();
        return TRUE;
    case WM_PAINT:
    {
        PAINTSTRUCT paint{};
        BeginPaint(hWnd, &paint);
        EndPaint(hWnd, &paint);
        g_redrawRequested = true;
        return 0;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    case WM_KEYDOWN:
        if (wParam == VK_ESCAPE)
            PostQuitMessage(0);
        return 0;
    }
    return DefWindowProc(hWnd, message, wParam, lParam);
}

void LogFailure(const wchar_t* operation, HRESULT result)
{
    wchar_t message[256];
    swprintf_s(message, L"Aurora: %ls failed (0x%08lx).\n", operation, static_cast<unsigned long>(result));
    OutputDebugStringW(message);
}

class WicLifetime
{
public:
    WicLifetime() : initialized(CoInitializeEx(nullptr, COINIT_MULTITHREADED))
    {
        if (SUCCEEDED(initialized) || initialized == RPC_E_CHANGED_MODE)
        {
            HRESULT result = CoCreateInstance(CLSID_WICImagingFactory, nullptr,
                CLSCTX_INPROC_SERVER, IID_PPV_ARGS(g_wicFactory.GetAddressOf()));
            if (FAILED(result)) LogFailure(L"WIC initialization", result);
        }
        else LogFailure(L"COM initialization", initialized);
    }
    ~WicLifetime()
    {
        g_wicFactory.Reset();
        if (SUCCEEDED(initialized)) CoUninitialize();
    }
private:
    HRESULT initialized;
};

bool LoadPNGTexture(const wchar_t* filePath)
{
    if (!g_wicFactory) return false;
    Microsoft::WRL::ComPtr<IWICBitmapDecoder> decoder;
    Microsoft::WRL::ComPtr<IWICBitmapFrameDecode> frame;
    Microsoft::WRL::ComPtr<IWICFormatConverter> converter;
    HRESULT result = g_wicFactory->CreateDecoderFromFilename(filePath, nullptr,
        GENERIC_READ, WICDecodeMetadataCacheOnDemand, decoder.GetAddressOf());
    if (SUCCEEDED(result)) result = decoder->GetFrame(0, frame.GetAddressOf());
    UINT width = 0, height = 0;
    if (SUCCEEDED(result)) result = frame->GetSize(&width, &height);
    constexpr std::size_t maxImagePixels = 16 * 1024 * 1024; // 64 MiB decoded maximum.
    if (SUCCEEDED(result) && (!width || !height || width > 32768 || height > 32768 ||
        static_cast<std::size_t>(width) * height > maxImagePixels))
        result = E_INVALIDARG;
    if (SUCCEEDED(result)) result = g_wicFactory->CreateFormatConverter(converter.GetAddressOf());
    // WIC handles RGB/RGBA and packed 1/2/4/8-bit palettes consistently. A top-down
    // premultiplied BGRA image also avoids resampling unassociated color fringes.
    if (SUCCEEDED(result)) result = converter->Initialize(frame.Get(), GUID_WICPixelFormat32bppPBGRA,
        WICBitmapDitherTypeNone, nullptr, 0.0, WICBitmapPaletteTypeCustom);
    if (FAILED(result))
    {
        LogFailure(L"PNG decode/conversion", result);
        return false; // Preserve the last good image.
    }
    try
    {
        std::vector<std::uint32_t> decoded(static_cast<std::size_t>(width) * height);
        result = converter->CopyPixels(nullptr, width * 4,
            static_cast<UINT>(decoded.size() * sizeof(std::uint32_t)), reinterpret_cast<BYTE*>(decoded.data()));
        if (FAILED(result))
        {
            LogFailure(L"PNG pixel copy", result);
            return false;
        }
        g_crosshairPixels.swap(decoded);
    }
    catch (const std::bad_alloc&)
    {
        LogFailure(L"PNG allocation", E_OUTOFMEMORY);
        return false;
    }
    g_textureWidth = static_cast<int>(width);
    g_textureHeight = static_cast<int>(height);
    g_textureLoaded = true;
    ++g_imageRevision;
    return true;
}

class LayeredSurface
{
public:
    ~LayeredSurface() { Reset(); }
    bool Ensure(int newWidth, int newHeight)
    {
        if (bitmap && width == newWidth && height == newHeight) return true;
        constexpr std::size_t maxSurfacePixels = 64 * 1024 * 1024; // 256 MiB, including 8K.
        if (newWidth <= 0 || newHeight <= 0 ||
            static_cast<std::size_t>(newWidth) * newHeight > maxSurfacePixels) return false;
        if (!dc) dc = CreateCompatibleDC(nullptr);
        if (!dc) return false;
        BITMAPINFO info{};
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = newWidth;
        info.bmiHeader.biHeight = -newHeight; // Top-down pixels, matching WIC.
        info.bmiHeader.biPlanes = 1;
        info.bmiHeader.biBitCount = 32;
        info.bmiHeader.biCompression = BI_RGB;
        void* bits = nullptr;
        HBITMAP replacement = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &bits, nullptr, 0);
        if (!replacement) return false;
        HGDIOBJ selected = SelectObject(dc, replacement);
        if (!selected || selected == HGDI_ERROR)
        {
            DeleteObject(replacement);
            return false;
        }
        if (!bitmap) original = selected;
        else DeleteObject(bitmap); // The old bitmap is now deselected.
        bitmap = replacement;
        pixels = static_cast<std::uint32_t*>(bits);
        width = newWidth;
        height = newHeight;
        revision = std::numeric_limits<std::uint64_t>::max();
        return true;
    }
    void Reset()
    {
        if (dc && original) SelectObject(dc, original);
        if (bitmap) DeleteObject(bitmap);
        if (dc) DeleteDC(dc);
        dc = nullptr; bitmap = nullptr; original = nullptr; pixels = nullptr;
    }
    HDC dc = nullptr;
    std::uint32_t* pixels = nullptr;
    int width = 0, height = 0;
    std::uint64_t revision = std::numeric_limits<std::uint64_t>::max();
    float scale = 0;
    int sourceX = 0, sourceY = 0;
    bool fallback = false;
private:
    HBITMAP bitmap = nullptr;
    HGDIOBJ original = nullptr;
};
LayeredSurface g_surface;

enum class ConfigReadResult { Applied, Missing, Retry, Rejected };

ConfigReadResult LoadConfiguration(bool& changed)
{
    changed = false;
    // Delete sharing permits the GUI's atomic os.replace. Omitting write sharing
    // prevents a normal in-place editor from being read halfway through a write.
    HANDLE file = CreateFileW(NativePath(g_configPath).c_str(), GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
    {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) return ConfigReadResult::Missing;
        return ConfigReadResult::Retry;
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size) || size.QuadPart < 0 || size.QuadPart > 64 * 1024)
    {
        CloseHandle(file);
        return ConfigReadResult::Rejected;
    }
    std::string bytes(static_cast<std::size_t>(size.QuadPart), '\0');
    DWORD count = 0;
    bool read = ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &count, nullptr) != FALSE;
    CloseHandle(file);
    if (!read || count != bytes.size()) return ConfigReadResult::Retry;
    aurora::Settings candidate = g_settings;
    if (!aurora::ParseSettings(bytes, candidate)) return ConfigReadResult::Rejected;
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, candidate.crosshair.data(),
        static_cast<int>(candidate.crosshair.size()), nullptr, 0);
    if (!length) return ConfigReadResult::Rejected;
    std::wstring name(static_cast<std::size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, candidate.crosshair.data(),
        static_cast<int>(candidate.crosshair.size()), name.data(), length);
    changed = candidate.scale != g_settings.scale || candidate.crosshair != g_settings.crosshair;
    g_settings = std::move(candidate);
    g_scale = g_settings.scale;
    g_crosshairName = std::move(name);
    return ConfigReadResult::Applied;
}

void RenderCrosshair()
{
    const bool fallback = !g_textureLoaded || g_useFallback;
    const int imageWidth = fallback ? 2 * g_crosshairSize : g_textureWidth;
    const int imageHeight = fallback ? 2 * g_crosshairSize : g_textureHeight;
    const float scale = fallback ? 1.0f : g_scale;
    const auto layout = aurora::ComputeLayout(g_screenLeft, g_screenTop, g_screenWidth, g_screenHeight,
        imageWidth, imageHeight, scale);
    if (!g_surface.Ensure(layout.width, layout.height))
    {
        LogFailure(L"layered surface allocation", E_OUTOFMEMORY);
        return;
    }
    if (g_surface.revision != g_imageRevision || g_surface.scale != scale ||
        g_surface.sourceX != layout.sourceX || g_surface.sourceY != layout.sourceY ||
        g_surface.fallback != fallback)
    {
        for (int y = 0; y < layout.height; ++y)
        {
            for (int x = 0; x < layout.width; ++x)
            {
                std::uint32_t pixel = 0;
                if (!fallback)
                    pixel = aurora::SampleBilinearPremultiplied(g_crosshairPixels.data(),
                        g_textureWidth, g_textureHeight,
                        static_cast<float>(x + layout.sourceX) / scale,
                        static_cast<float>(y + layout.sourceY) / scale);
                else
                {
                    const int imageX = x + layout.sourceX;
                    const int imageY = y + layout.sourceY;
                    const int halfThickness = g_crosshairThickness / 2;
                    if ((imageX >= imageWidth / 2 - halfThickness && imageX < imageWidth / 2 + halfThickness) ||
                        (imageY >= imageHeight / 2 - halfThickness && imageY < imageHeight / 2 + halfThickness))
                        pixel = 0xffff66cc; // Opaque pink in premultiplied BGRA.
                }
                g_surface.pixels[static_cast<std::size_t>(y) * layout.width + x] = pixel;
            }
        }
        g_surface.revision = g_imageRevision;
        g_surface.scale = scale;
        g_surface.sourceX = layout.sourceX;
        g_surface.sourceY = layout.sourceY;
        g_surface.fallback = fallback;
    }
    POINT destination{layout.left, layout.top};
    POINT source{};
    SIZE size{layout.width, layout.height};
    BLENDFUNCTION blend{AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};
    // Windows retains this layered bitmap while the application waits for events.
    if (!UpdateLayeredWindow(g_hWnd, nullptr, &destination, &size, g_surface.dc,
        &source, 0, &blend, ULW_ALPHA))
        LogFailure(L"UpdateLayeredWindow", HRESULT_FROM_WIN32(GetLastError()));
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE, PWSTR, int)
{
    EnablePhysicalPixelCoordinates(); // Must precede HWND creation and monitor queries.
    WicLifetime wic;
    g_configDirectory = EnvironmentValue(L"AURORA_OVERLAY_HOME");
    if (g_configDirectory.empty())
        g_configDirectory = EnvironmentValue(L"USERPROFILE") + L"\\Documents\\Crosshair overlay";
    std::error_code pathError;
    auto absoluteHome = std::filesystem::absolute(g_configDirectory, pathError);
    if (!pathError)
    {
        absoluteHome = absoluteHome.lexically_normal();
        // Strip a trailing separator without stripping the root itself.
        while (absoluteHome != absoluteHome.root_path() && absoluteHome.filename().empty())
            absoluteHome = absoluteHome.parent_path();
        g_configDirectory = absoluteHome.wstring();
    }
    auto parentDirectory = std::filesystem::path(g_configDirectory).parent_path();
    if (parentDirectory != std::filesystem::path(g_configDirectory))
        g_configParentDirectory = parentDirectory.wstring();
    g_configPath = (std::filesystem::path(g_configDirectory) / L"overlay_config.txt").wstring();
    g_resourceDirectory = FindResources();
    RefreshMonitorGeometry();

    // Register window class
    WNDCLASSEX wcex{};
    wcex.cbSize = sizeof(wcex);
    wcex.lpfnWndProc = WndProc;
    wcex.hInstance = hInstance;
    wcex.lpszClassName = L"AuroraCrosshair";
    if (!RegisterClassEx(&wcex))
    {
        LogFailure(L"window class registration", HRESULT_FROM_WIN32(GetLastError()));
        return 1;
    }

    // Create layered window for transparency support
    g_hWnd = CreateWindowEx(
        WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE,
        L"AuroraCrosshair",
        L"Aurora Crosshair",
        WS_POPUP,
        g_screenLeft, g_screenTop, 1, 1,
        nullptr, nullptr, hInstance, nullptr);

    if (!g_hWnd)
    {
        LogFailure(L"window creation", HRESULT_FROM_WIN32(GetLastError()));
        UnregisterClassW(L"AuroraCrosshair", hInstance);
        return 1;
    }

    // Preserve existing capture affinity; this does not override exclusive fullscreen.
    SetWindowDisplayAffinity(g_hWnd, WDA_MONITOR);

    ShowWindow(g_hWnd, SW_SHOWNOACTIVATE);
    UpdateWindow(g_hWnd);

    // Arm notifications before reading so startup changes cannot be lost.
    HANDLE directoryWatch = WatchConfigurationDirectory();
    HANDLE parentWatch = WatchConfigurationParent();
    const bool needsParentWatch = !g_configParentDirectory.empty();
    ConfigStamp configStamp;
    ConfigurationChanged(configStamp);
    bool configurationChanged = false;
    ConfigReadResult initialRead = LoadConfiguration(configurationChanged);
    if (initialRead == ConfigReadResult::Rejected)
        OutputDebugStringW(L"Aurora: invalid configuration; keeping defaults.\n");
    bool readPending = initialRead == ConfigReadResult::Retry;
    unsigned readAttempts = 0;
    ULONGLONG nextRead = GetTickCount64() + 50;
    LoadPNGTexture(SelectedTexturePath().c_str());

    MSG msg{};
    int exitCode = 0;
    bool running = true;
    while (running)
    {
        while (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE))
        {
            if (msg.message == WM_QUIT)
            {
                running = false;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        if (!running) break;
        if (readPending && GetTickCount64() >= nextRead)
        {
            std::wstring previousName = g_crosshairName;
            bool changed = false;
            ConfigReadResult read = LoadConfiguration(changed);
            if (read == ConfigReadResult::Retry && ++readAttempts < 10)
                nextRead = GetTickCount64() + 50; // Bounded retries during an update only.
            else
            {
                readPending = false;
                ConfigurationChanged(configStamp);
                if (read == ConfigReadResult::Rejected || read == ConfigReadResult::Retry)
                    OutputDebugStringW(L"Aurora: configuration unreadable/invalid; retaining last valid settings.\n");
            }
            if (previousName != g_crosshairName)
                LoadPNGTexture(SelectedTexturePath().c_str());
            if (changed) g_redrawRequested = true;
        }
        if (g_redrawRequested)
        {
            g_redrawRequested = false;
            RenderCrosshair();
        }

        HANDLE waits[2];
        DWORD waitCount = 0;
        DWORD directoryIndex = MAXDWORD, parentIndex = MAXDWORD;
        if (directoryWatch != INVALID_HANDLE_VALUE)
        {
            directoryIndex = waitCount;
            waits[waitCount++] = directoryWatch;
        }
        if (parentWatch != INVALID_HANDLE_VALUE)
        {
            parentIndex = waitCount;
            waits[waitCount++] = parentWatch;
        }
        bool notificationsComplete = directoryWatch != INVALID_HANDLE_VALUE &&
            (!needsParentWatch || parentWatch != INVALID_HANDLE_VALUE);
        DWORD timeout = notificationsComplete ? INFINITE : 1000;
        if (readPending)
        {
            ULONGLONG now = GetTickCount64();
            DWORD delay = nextRead > now ? static_cast<DWORD>(nextRead - now) : 0;
            timeout = std::min(timeout, delay);
        }
        DWORD result = MsgWaitForMultipleObjectsEx(waitCount, waits, timeout,
            QS_ALLINPUT, MWMO_INPUTAVAILABLE);
        bool inspectConfiguration = false;
        if (directoryIndex != MAXDWORD && result == WAIT_OBJECT_0 + directoryIndex)
        {
            // Rearm first: atomic rename and rapid consecutive writes must be seen.
            if (!FindNextChangeNotification(directoryWatch)) CloseDirectoryWatch(directoryWatch);
            inspectConfiguration = true;
        }
        else if (parentIndex != MAXDWORD && result == WAIT_OBJECT_0 + parentIndex)
        {
            // A moved directory can retain a perfectly valid contents watch on
            // its old identity. Rebind to the configured path after parent name
            // changes, including replacement/recreation of the whole directory.
            if (!FindNextChangeNotification(parentWatch)) CloseDirectoryWatch(parentWatch);
            CloseDirectoryWatch(directoryWatch);
            directoryWatch = WatchConfigurationDirectory();
            inspectConfiguration = true;
        }
        else if (!notificationsComplete && !readPending && result == WAIT_TIMEOUT)
        {
            // Degraded fallback only: one metadata check/second, never an idle
            // redraw. Retry missing/unsupported watches without another thread.
            bool recovered = false;
            if (needsParentWatch && parentWatch == INVALID_HANDLE_VALUE)
            {
                parentWatch = WatchConfigurationParent();
                if (parentWatch != INVALID_HANDLE_VALUE)
                {
                    CloseDirectoryWatch(directoryWatch);
                    recovered = true;
                }
            }
            if (directoryWatch == INVALID_HANDLE_VALUE)
            {
                directoryWatch = WatchConfigurationDirectory();
                recovered = recovered || directoryWatch != INVALID_HANDLE_VALUE;
            }
            bool stampChanged = ConfigurationChanged(configStamp);
            inspectConfiguration = recovered || stampChanged;
        }
        else if (result == WAIT_FAILED)
        {
            LogFailure(L"window/configuration wait", HRESULT_FROM_WIN32(GetLastError()));
            exitCode = 1;
            break;
        }
        if (inspectConfiguration && !readPending)
        {
            // A rename can replace a file while preserving its size/timestamp.
            // Notifications therefore read unconditionally; only fallback polling
            // uses metadata gating. Briefly debounce bursts from atomic saves.
            readPending = true;
            readAttempts = 0;
            nextRead = GetTickCount64() + 50;
        }
    }
    CloseDirectoryWatch(directoryWatch);
    CloseDirectoryWatch(parentWatch);
    if (IsWindow(g_hWnd)) DestroyWindow(g_hWnd);
    UnregisterClassW(L"AuroraCrosshair", hInstance);

    g_surface.Reset();
    g_crosshairPixels.clear();

    return exitCode ? exitCode : static_cast<int>(msg.wParam);
}
