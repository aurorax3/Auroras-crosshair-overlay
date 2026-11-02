#include <windows.h>
#include <wincodec.h>
#include <cstdio>
#include <cstring>
#include <tuple>
#include <string>

#pragma comment(lib, "windowscodecs.lib")

HWND g_hWnd = nullptr;
int g_crosshairSize = 20;
int g_crosshairThickness = 3;
int g_screenWidth = 0;
int g_screenHeight = 0;
DWORD* g_crosshairTexture = nullptr;
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
        SetWindowPos(hWnd, HWND_TOPMOST, 0, 0, g_screenWidth, g_screenHeight, SWP_NOACTIVATE);
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

bool LoadPNGTexture(const wchar_t* filePath)
{
    // Initialize COM for WIC
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    
    // Create WIC factory
    IWICImagingFactory* pFactory = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&pFactory));
    if (FAILED(hr))
    {
        CoUninitialize();
        return false;
    }
    
    // Load the image
    IWICBitmapDecoder* pDecoder = nullptr;
    hr = pFactory->CreateDecoderFromFilename(filePath, nullptr, GENERIC_READ, WICDecodeMetadataCacheOnDemand, &pDecoder);
    if (FAILED(hr))
    {
        pFactory->Release();
        CoUninitialize();
        return false;
    }
    
    // Get the first frame
    IWICBitmapFrameDecode* pFrame = nullptr;
    hr = pDecoder->GetFrame(0, &pFrame);
    if (FAILED(hr))
    {
        pDecoder->Release();
        pFactory->Release();
        CoUninitialize();
        return false;
    }
    
    // Get frame dimensions
    UINT width = 0, height = 0;
    pFrame->GetSize(&width, &height);
    g_textureWidth = width;
    g_textureHeight = height;
    
    // Allocate texture buffer
    if (g_crosshairTexture)
        delete[] g_crosshairTexture;
    
    g_crosshairTexture = new DWORD[width * height];
    memset(g_crosshairTexture, 0, width * height * sizeof(DWORD));
    
    // Get pixel format
    WICPixelFormatGUID pixelFormat;
    pFrame->GetPixelFormat(&pixelFormat);
    
    // Handle indexed color (palette) images
    if (pixelFormat == GUID_WICPixelFormat8bppIndexed || 
        pixelFormat == GUID_WICPixelFormat4bppIndexed ||
        pixelFormat == GUID_WICPixelFormat2bppIndexed ||
        pixelFormat == GUID_WICPixelFormat1bppIndexed)
    {
        // Get the palette
        IWICPalette* pPalette = nullptr;
        hr = pFactory->CreatePalette(&pPalette);
        if (SUCCEEDED(hr))
        {
            hr = pFrame->CopyPalette(pPalette);
            if (SUCCEEDED(hr))
            {
                UINT paletteSize = 0;
                pPalette->GetColorCount(&paletteSize);
                
                WICColor* paletteColors = new WICColor[paletteSize];
                pPalette->GetColors(paletteSize, paletteColors, &paletteSize);
                
                // Read indexed pixel data
                int bytesPerPixel = 1;  // Most common for indexed
                UINT stride = width * bytesPerPixel;
                BYTE* indexedData = new BYTE[width * height];
                
                hr = pFrame->CopyPixels(nullptr, stride, height * stride, indexedData);
                
                if (SUCCEEDED(hr))
                {
                    // Convert indexed to BGRA using palette and flip vertically
                    for (UINT y = 0; y < height; y++)
                    {
                        for (UINT x = 0; x < width; x++)
                        {
                            UINT srcIdx = y * width + x;
                            UINT dstIdx = (height - 1 - y) * width + x;
                            
                            BYTE index = indexedData[srcIdx];
                            if (index < paletteSize)
                            {
                                WICColor color = paletteColors[index];
                                // WICColor is ARGB format
                                BYTE a = (color >> 24) & 0xFF;
                                BYTE r = (color >> 16) & 0xFF;
                                BYTE g = (color >> 8) & 0xFF;
                                BYTE b = (color >> 0) & 0xFF;
                                
                                // Convert to BGRA
                                g_crosshairTexture[dstIdx] = (a << 24) | (r << 16) | (g << 8) | b;
                            }
                        }
                    }
                }
                
                delete[] indexedData;
                delete[] paletteColors;
            }
            pPalette->Release();
        }
    }
    else
    {
        // Non-indexed formats - read directly
        BYTE* tempBuffer = new BYTE[width * height * 4];
        memset(tempBuffer, 0, width * height * 4);
        
        hr = pFrame->CopyPixels(nullptr, width * 4, width * height * 4, tempBuffer);
        
        if (SUCCEEDED(hr))
        {
            // Flip vertically while copying - PNG is top-down, we need bottom-up
            for (UINT y = 0; y < height; y++)
            {
                for (UINT x = 0; x < width; x++)
                {
                    UINT srcIdx = y * width * 4 + x * 4;
                    UINT dstIdx = (height - 1 - y) * width * 4 + x * 4;
                    
                    g_crosshairTexture[dstIdx / 4] = *(DWORD*)(tempBuffer + srcIdx);
                }
            }
        }
        
        delete[] tempBuffer;
    }
    
    // Cleanup
    pFrame->Release();
    pDecoder->Release();
    pFactory->Release();
    CoUninitialize();
    
    bool success = SUCCEEDED(hr);
    g_textureLoaded = success;
    return success;
}

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
    // Create a memory DC for off-screen rendering
    HDC hdcScreen = GetDC(nullptr);
    HDC hdcMem = CreateCompatibleDC(hdcScreen);
    
    // Create a 32-bit DIB (Device Independent Bitmap) for alpha blending
    BITMAPV5HEADER bi = {};
    bi.bV5Size = sizeof(BITMAPV5HEADER);
    bi.bV5Width = g_screenWidth;
    bi.bV5Height = g_screenHeight;
    bi.bV5Planes = 1;
    bi.bV5BitCount = 32;
    bi.bV5Compression = BI_BITFIELDS;
    bi.bV5RedMask = 0x00FF0000;
    bi.bV5GreenMask = 0x0000FF00;
    bi.bV5BlueMask = 0x000000FF;
    bi.bV5AlphaMask = 0xFF000000;
    
    void* pvBits = nullptr;
    HBITMAP hbmMem = CreateDIBSection(hdcMem, (BITMAPINFO*)&bi, DIB_RGB_COLORS, &pvBits, nullptr, 0);
    
    if (!hbmMem || !pvBits)
    {
        DeleteDC(hdcMem);
        ReleaseDC(nullptr, hdcScreen);
        return;
    }
    
    HBITMAP hbmOld = (HBITMAP)SelectObject(hdcMem, hbmMem);
    
    // Clear to transparent (0,0,0,0)
    DWORD* pixels = (DWORD*)pvBits;
    for (int i = 0; i < g_screenWidth * g_screenHeight; i++)
        pixels[i] = 0;  // ARGB: 0 = fully transparent
    
    // If texture is loaded and we have it, draw it centered with scale
    if (g_textureLoaded && !g_useFallback && g_crosshairTexture && g_textureWidth > 0 && g_textureHeight > 0)
    {
        int scaledWidth = (int)(g_textureWidth * g_scale);
        int scaledHeight = (int)(g_textureHeight * g_scale);
        
        int centerX = g_screenWidth / 2;
        int centerY = g_screenHeight / 2;
        int startX = centerX - scaledWidth / 2;
        int startY = centerY - scaledHeight / 2;
        
        // Use bilinear interpolation for smooth scaling
        for (int y = 0; y < scaledHeight; y++)
        {
            for (int x = 0; x < scaledWidth; x++)
            {
                int screenX = startX + x;
                int screenY = startY + y;
                
                // Bounds check
                if (screenX >= 0 && screenX < g_screenWidth && screenY >= 0 && screenY < g_screenHeight)
                {
                    // Sample from original texture with bilinear interpolation
                    float srcXf = (float)x / g_scale;
                    float srcYf = (float)y / g_scale;
                    
                    int srcX0 = (int)srcXf;
                    int srcY0 = (int)srcYf;
                    int srcX1 = srcX0 + 1;
                    int srcY1 = srcY0 + 1;
                    
                    float fracX = srcXf - srcX0;
                    float fracY = srcYf - srcY0;
                    
                    // Clamp to texture bounds
                    if (srcX0 >= 0 && srcX0 < g_textureWidth && srcY0 >= 0 && srcY0 < g_textureHeight)
                    {
                        // Get four corner texels
                        DWORD texel00 = g_crosshairTexture[srcY0 * g_textureWidth + srcX0];
                        DWORD texel10 = (srcX1 < g_textureWidth) ? g_crosshairTexture[srcY0 * g_textureWidth + srcX1] : texel00;
                        DWORD texel01 = (srcY1 < g_textureHeight) ? g_crosshairTexture[srcY1 * g_textureWidth + srcX0] : texel00;
                        DWORD texel11 = (srcX1 < g_textureWidth && srcY1 < g_textureHeight) ? g_crosshairTexture[srcY1 * g_textureWidth + srcX1] : texel00;
                        
                        // Extract BGRA components for each corner
                        auto getComponents = [](DWORD texel) -> std::tuple<float, float, float, float> {
                            return std::make_tuple(
                                (float)((texel >> 0) & 0xFF),   // B
                                (float)((texel >> 8) & 0xFF),   // G
                                (float)((texel >> 16) & 0xFF),  // R
                                (float)((texel >> 24) & 0xFF)   // A
                            );
                        };
                        
                        auto [b00, g00, r00, a00] = getComponents(texel00);
                        auto [b10, g10, r10, a10] = getComponents(texel10);
                        auto [b01, g01, r01, a01] = getComponents(texel01);
                        auto [b11, g11, r11, a11] = getComponents(texel11);
                        
                        // Bilinear interpolation
                        float b = b00 * (1 - fracX) * (1 - fracY) + b10 * fracX * (1 - fracY) + 
                                  b01 * (1 - fracX) * fracY + b11 * fracX * fracY;
                        float g_val = g00 * (1 - fracX) * (1 - fracY) + g10 * fracX * (1 - fracY) + 
                                      g01 * (1 - fracX) * fracY + g11 * fracX * fracY;
                        float r = r00 * (1 - fracX) * (1 - fracY) + r10 * fracX * (1 - fracY) + 
                                  r01 * (1 - fracX) * fracY + r11 * fracX * fracY;
                        float a = a00 * (1 - fracX) * (1 - fracY) + a10 * fracX * (1 - fracY) + 
                                  a01 * (1 - fracX) * fracY + a11 * fracX * fracY;
                        
                        // Only blend if alpha > threshold
                        if (a > 1.0f)
                        {
                            // Premultiply alpha for proper blending
                            BYTE premulR = (BYTE)((r * a) / 255.0f);
                            BYTE premulG = (BYTE)((g_val * a) / 255.0f);
                            BYTE premulB = (BYTE)((b * a) / 255.0f);
                            BYTE alphaVal = (BYTE)a;
                            
                            int screenIdx = screenY * g_screenWidth + screenX;
                            DWORD blended = (alphaVal << 24) | (premulR << 16) | (premulG << 8) | premulB;
                            pixels[screenIdx] = blended;
                        }
                    }
                }
            }
        }
    }
    else
    {
        // Fallback: Draw pink crosshair
        HBRUSH pinkBrush = CreateSolidBrush(RGB(255, 102, 204));
        
        int centerX = g_screenWidth / 2;
        int centerY = g_screenHeight / 2;
        
        // Horizontal bar
        RECT hBar = {
            centerX - g_crosshairSize,
            centerY - g_crosshairThickness / 2,
            centerX + g_crosshairSize,
            centerY + g_crosshairThickness / 2
        };
        FillRect(hdcMem, &hBar, pinkBrush);
        
        // Vertical bar
        RECT vBar = {
            centerX - g_crosshairThickness / 2,
            centerY - g_crosshairSize,
            centerX + g_crosshairThickness / 2,
            centerY + g_crosshairSize
        };
        FillRect(hdcMem, &vBar, pinkBrush);
        
        // Manually set alpha for pink pixels
        pixels = (DWORD*)pvBits;
        DWORD pinkColor = RGB(255, 102, 204);
        
        for (int i = 0; i < g_screenWidth * g_screenHeight; i++)
        {
            if ((pixels[i] & 0x00FFFFFF) == pinkColor)
                pixels[i] |= 0xFF000000;  // Set alpha to fully opaque
        }
        
        DeleteObject(pinkBrush);
    }
    
    // Update layered window with the bitmap
    SIZE sizeWnd = { g_screenWidth, g_screenHeight };
    POINT ptSrc = { 0, 0 };
    BLENDFUNCTION blendFunc = {};
    blendFunc.BlendOp = AC_SRC_OVER;
    blendFunc.BlendFlags = 0;
    blendFunc.AlphaFormat = AC_SRC_ALPHA;
    blendFunc.SourceConstantAlpha = 255;
    
    UpdateLayeredWindow(g_hWnd, hdcScreen, nullptr, &sizeWnd, hdcMem, &ptSrc, 0, &blendFunc, ULW_ALPHA);
    
    // Cleanup
    SelectObject(hdcMem, hbmOld);
    DeleteObject(hbmMem);
    DeleteDC(hdcMem);
    ReleaseDC(nullptr, hdcScreen);
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow)
{
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

    // Cleanup
    if (g_crosshairTexture)
        delete[] g_crosshairTexture;

    return (int)msg.wParam;
}
