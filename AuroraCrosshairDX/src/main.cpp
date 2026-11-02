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
#include <wrl/client.h>
#include "OverlayLogic.h"

#pragma comment(lib, "windowscodecs.lib")

HWND g_hWnd = nullptr;
int g_crosshairSize = 20;
int g_crosshairThickness = 3;
int g_screenWidth = 0;
int g_screenHeight = 0;
std::vector<std::uint32_t> g_crosshairPixels;
std::uint64_t g_imageRevision = 0;
Microsoft::WRL::ComPtr<IWICImagingFactory> g_wicFactory;
int g_textureWidth = 0;
int g_textureHeight = 0;
float g_scale = 1.0f;  // Scale multiplier (1.0 = 100%)
wchar_t g_crosshairName[256] = L"osupink.png";  // Current crosshair filename
bool g_textureLoaded = false;  // Track if texture successfully loaded
bool g_useFallback = false;  // Force use fallback pink crosshair
bool g_redrawRequested = true;
std::wstring g_configDirectory;
std::wstring g_configPath;

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
    current.exists = GetFileAttributesExW(g_configPath.c_str(), GetFileExInfoStandard, &info) != FALSE;
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
    return FindFirstChangeNotificationW(g_configDirectory.c_str(), FALSE,
        FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_LAST_WRITE | FILE_NOTIFY_CHANGE_SIZE);
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    switch (message)
    {
    case WM_CLOSE:
        DestroyWindow(hWnd);
        return 0;
    case WM_DISPLAYCHANGE:
        g_screenWidth = GetSystemMetrics(SM_CXSCREEN);
        g_screenHeight = GetSystemMetrics(SM_CYSCREEN);
        g_redrawRequested = true;
        return 0;
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
    swprintf_s(message, L"Aurora: %s failed (0x%08lx).\n", operation, static_cast<unsigned long>(result));
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

void LoadConfiguration()
{
    // Read scale and crosshair settings from a text file in Documents
    FILE* file = nullptr;
    errno_t err = _wfopen_s(&file, g_configPath.c_str(), L"r");
    if (err == 0 && file)
    {
        wchar_t line[256];
        while (fgetws(line, 256, file))
        {
            // Parse scale: scale=1.5
            if (wcsncmp(line, L"scale=", 6) == 0)
            {
                g_scale = _wtof(line + 6);
                if (g_scale < 0.5f) g_scale = 0.5f;
                if (g_scale > 3.0f) g_scale = 3.0f;
            }
            // Parse crosshair: crosshair=osupink.png
            else if (wcsncmp(line, L"crosshair=", 10) == 0)
            {
                wcscpy_s(g_crosshairName, 256, line + 10);
                // Remove trailing newline
                size_t len = wcslen(g_crosshairName);
                if (len > 0 && g_crosshairName[len - 1] == L'\n')
                    g_crosshairName[len - 1] = L'\0';
            }
        }
        fclose(file);
    }
}

void RenderCrosshair()
{
    const bool fallback = !g_textureLoaded || g_useFallback;
    const int imageWidth = fallback ? 2 * g_crosshairSize : g_textureWidth;
    const int imageHeight = fallback ? 2 * g_crosshairSize : g_textureHeight;
    const float scale = fallback ? 1.0f : g_scale;
    const auto layout = aurora::ComputeLayout(0, 0, g_screenWidth, g_screenHeight,
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

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow)
{
    WicLifetime wic;
    g_configDirectory = EnvironmentValue(L"AURORA_OVERLAY_HOME");
    if (g_configDirectory.empty())
        g_configDirectory = EnvironmentValue(L"USERPROFILE") + L"\\Documents\\Crosshair overlay";
    g_configPath = g_configDirectory + L"\\overlay_config.txt";

    // Get primary monitor resolution
    g_screenWidth = GetSystemMetrics(SM_CXSCREEN);
    g_screenHeight = GetSystemMetrics(SM_CYSCREEN);
    
    // Get the directory where the executable is located
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    
    // Remove the exe filename to get the directory
    wchar_t* lastSlash = wcsrchr(exePath, L'\\');
    if (lastSlash)
        *lastSlash = L'\0';
    
    // Build path to resources: exe is in x64\Release, go up two directories to project root
    wchar_t resourceDir[MAX_PATH];
    wcscpy_s(resourceDir, MAX_PATH, exePath);
    
    // Go up one level: x64\Release -> x64
    lastSlash = wcsrchr(resourceDir, L'\\');
    if (lastSlash)
        *lastSlash = L'\0';
    
    // Go up one more level: x64 -> AuroraCrosshairDX
    lastSlash = wcsrchr(resourceDir, L'\\');
    if (lastSlash)
        *lastSlash = L'\0';
    

    // Register window class
    WNDCLASSEX wcex = { sizeof(WNDCLASSEX) };
    wcex.lpfnWndProc = WndProc;
    wcex.hInstance = hInstance;
    wcex.lpszClassName = L"AuroraCrosshair";
    RegisterClassEx(&wcex);

    // Create layered window for transparency support
    g_hWnd = CreateWindowEx(
        WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE,
        L"AuroraCrosshair",
        L"Aurora Crosshair",
        WS_POPUP,
        0, 0, g_screenWidth, g_screenHeight,
        nullptr, nullptr, hInstance, nullptr);

    if (!g_hWnd)
        return -1;

    // Preserve existing capture affinity; this does not override exclusive fullscreen.
    SetWindowDisplayAffinity(g_hWnd, WDA_MONITOR);

    ShowWindow(g_hWnd, SW_SHOW);
    UpdateWindow(g_hWnd);

    // Arm notifications before reading so startup changes cannot be lost.
    HANDLE directoryWatch = WatchConfigurationDirectory();
    ConfigStamp configStamp;
    ConfigurationChanged(configStamp);
    LoadConfiguration();
    wchar_t texturePath[MAX_PATH];
    swprintf_s(texturePath, MAX_PATH, L"%s\\resources\\crosshairs\\%s", resourceDir, g_crosshairName);
    LoadPNGTexture(texturePath);

    MSG msg{};
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
        if (g_redrawRequested)
        {
            g_redrawRequested = false;
            RenderCrosshair();
        }

        bool watching = directoryWatch != INVALID_HANDLE_VALUE;
        DWORD result = MsgWaitForMultipleObjectsEx(watching ? 1 : 0,
            watching ? &directoryWatch : nullptr, watching ? INFINITE : 1000,
            QS_ALLINPUT, MWMO_INPUTAVAILABLE);
        bool inspectConfiguration = false;
        if (watching && result == WAIT_OBJECT_0)
        {
            // Rearm first: atomic rename and rapid consecutive writes must be seen.
            if (!FindNextChangeNotification(directoryWatch))
            {
                FindCloseChangeNotification(directoryWatch);
                directoryWatch = INVALID_HANDLE_VALUE;
            }
            inspectConfiguration = true;
        }
        else if (!watching && result == WAIT_TIMEOUT)
        {
            // Only when notifications are unavailable: one metadata check/second,
            // with disk parsing gated on a changed timestamp or length.
            directoryWatch = WatchConfigurationDirectory();
            inspectConfiguration = true;
        }
        else if (result == WAIT_FAILED)
        {
            OutputDebugStringW(L"Aurora: window/configuration wait failed.\n");
            break;
        }
        if (inspectConfiguration && ConfigurationChanged(configStamp))
        {
            std::wstring oldCrosshair = g_crosshairName;
            float oldScale = g_scale;
            LoadConfiguration();
            if (oldCrosshair != g_crosshairName)
            {
                swprintf_s(texturePath, MAX_PATH, L"%s\\resources\\crosshairs\\%s", resourceDir, g_crosshairName);
                LoadPNGTexture(texturePath);
            }
            if (oldCrosshair != g_crosshairName || oldScale != g_scale)
                g_redrawRequested = true;
        }
    }
    if (directoryWatch != INVALID_HANDLE_VALUE)
        FindCloseChangeNotification(directoryWatch);
    if (IsWindow(g_hWnd)) DestroyWindow(g_hWnd);
    UnregisterClassW(L"AuroraCrosshair", hInstance);

    g_surface.Reset();
    g_crosshairPixels.clear();

    return (int)msg.wParam;
}
