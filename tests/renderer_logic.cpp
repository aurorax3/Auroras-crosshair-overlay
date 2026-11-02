#include "OverlayLogic.h"

#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

namespace {
int checks = 0;
void Check(bool condition, const char* description)
{
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << description << '\n';
        std::exit(1);
    }
}

void TestConfiguration()
{
    aurora::Settings settings;
    Check(aurora::ParseSettings("scale=1.5\ncrosshair=dots/osupink.png\n", settings), "normal config");
    Check(settings.scale == 1.5f && settings.crosshair == "dots/osupink.png", "normal values");
    Check(aurora::ParseSettings("\xef\xbb\xbf# comment\r\n scale = +5e-1 \r\ncrosshair=other\\\xe7\x85\xa7\xe6\x98\x8e.png\r\nextra=future\r\n", settings), "BOM CRLF Unicode and future key");
    Check(settings.scale == 0.5f && settings.crosshair == "other/\xe7\x85\xa7\xe6\x98\x8e.png", "UTF8 and slash normalization");
    Check(aurora::ParseSettings("crosshair=circles/a.png\nscale=3", settings), "known keys in reverse order without final newline");
    Check(aurora::ParseSettings("scale=1.25\n", settings), "single scale key remains supported");
    Check(settings.scale == 1.25f && settings.crosshair == "circles/a.png", "omitted path preserves current image");
    Check(aurora::ParseSettings("crosshair=other/b.png\n", settings), "single path key remains supported");
    Check(settings.scale == 1.25f && settings.crosshair == "other/b.png", "omitted scale preserves current size");
    Check(aurora::ParseSettings("scale=0.49\n", settings) && settings.scale == 0.5f, "low scale clamps compatibly");
    Check(aurora::ParseSettings("scale=3.01\n", settings) && settings.scale == 3.0f, "high scale clamps compatibly");
    Check(aurora::ParseSettings("scale=-1\n", settings) && settings.scale == 0.5f, "negative finite scale clamps compatibly");
    Check(aurora::ParseSettings("scale=1e100\n", settings) && settings.scale == 3.0f, "large finite scale clamps before float conversion");
    const std::string component = std::string(251, 'a') + ".png";
    Check(aurora::ParseSettings("crosshair=" + component + "\n", settings), "255 character path component accepted");
    Check(!aurora::ParseSettings("crosshair=a" + component + "\n", settings), "256 character component rejected");
    std::string unicodeComponent;
    for (int i = 0; i < 251; ++i)
        unicodeComponent += "\xe7\x85\xa7";
    unicodeComponent += ".png";
    Check(aurora::ParseSettings("crosshair=" + unicodeComponent + "\n", settings), "component length counts Unicode characters, not bytes");
    std::string longPath;
    for (int i = 0; i < 16; ++i)
        longPath += std::string(252, 'a') + '/';
    longPath += std::string(44, 'b') + ".png";
    Check(longPath.size() == 4096 && aurora::ParseSettings("crosshair=" + longPath + "\n", settings), "4096 character relative path accepted");
    Check(!aurora::ParseSettings("crosshair=" + longPath + "a\n", settings), "4097 character path rejected");

    const std::string bad[] = {
        "", "# comment\n", "future=value\n", "scale=\ncrosshair=a.png\n",
        "scale=1\ncrosshair=\n", "scale=nan\ncrosshair=a.png\n",
        "scale=inf\ncrosshair=a.png\n", "scale=-inf\ncrosshair=a.png\n",
        "scale=1e1000\ncrosshair=a.png\n",
        "scale=1garbage\ncrosshair=a.png\n", "scale=++1\ncrosshair=a.png\n",
        "scale=1\nscale=2\ncrosshair=a.png\n", "scale=1\ncrosshair=a.png\ncrosshair=b.png\n",
        "scale=1\nthis is broken\ncrosshair=a.png\n", "scale=1\n=c\ncrosshair=a.png\n",
        "scale=1\ncrosshair=../a.png\n", "scale=1\ncrosshair=a/../b.png\n",
        "scale=1\ncrosshair=/absolute.png\n", "scale=1\ncrosshair=\\absolute.png\n",
        "scale=1\ncrosshair=C:\\a.png\n", "scale=1\ncrosshair=a.png:stream\n",
        "scale=1\ncrosshair=\\\\server\\share\\a.png\n", "scale=1\ncrosshair=a//b.png\n",
        "scale=1\ncrosshair=a/./b.png\n", "scale=1\ncrosshair=a/\n",
        "scale=1\ncrosshair=a?/b.png\n", "scale=1\ncrosshair=a. /b.png\n",
        "scale=1\ncrosshair=\xc0\xaf.png\n", "scale=1\ncrosshair=\xed\xa0\x80.png\n",
        "scale=1\ncrosshair=\xf4\x90\x80\x80.png\n", "scale=1\ncrosshair=\xe2\x82.png\n",
        std::string("scale=1\ncrosshair=a") + '\0' + ".png\n",
        std::string(65537, 'a')
    };
    for (const auto& bytes : bad) {
        const auto previous = settings;
        Check(!aurora::ParseSettings(bytes, settings), "invalid config rejected");
        Check(settings.scale == previous.scale && settings.crosshair == previous.crosshair,
              "invalid config cannot partially update settings");
    }
    Check(aurora::IsValidUtf8("\xf0\x9f\x8e\xaf.png"), "four-byte UTF8");
    Check(!aurora::IsValidUtf8("\x80"), "unexpected continuation byte");
}

void TestLayout()
{
    auto layout = aurora::ComputeLayout(0, 0, 1920, 1080, 20, 20, 1.5f);
    Check(layout.left == 945 && layout.top == 525 && layout.width == 30 && layout.height == 30,
          "small image has tight centered bounds");
    Check(layout.sourceX == 0 && layout.sourceY == 0, "small image not cropped");
    layout = aurora::ComputeLayout(-1920, -100, 1920, 1080, 21, 17, 1.0f);
    Check(layout.left == -970 && layout.top == 432 && layout.width == 21 && layout.height == 17,
          "negative monitor origin and odd pixel dimensions");
    layout = aurora::ComputeLayout(-100, 20, 100, 80, 200, 100, 1.0f);
    Check(layout.left == -100 && layout.top == 20 && layout.width == 100 && layout.height == 80 &&
          layout.sourceX == 50 && layout.sourceY == 10, "large image clips to monitor with centered source offset");
    layout = aurora::ComputeLayout(0, 0, 100, 100, 101, 103, 1.0f);
    Check(layout.sourceX == 0 && layout.sourceY == 1 && layout.width == 100 && layout.height == 100,
          "odd oversized images preserve original integer anchor");
    layout = aurora::ComputeLayout(0, 0, 100, 100, 1, 1, 0.5f);
    Check(layout.width == 1 && layout.height == 1, "subpixel scaled image remains visible");
    const float nan = std::numeric_limits<float>::quiet_NaN();
    const float infinity = std::numeric_limits<float>::infinity();
    Check(aurora::ComputeLayout(0, 0, 0, 10, 2, 2, 1).width == 0, "invalid monitor");
    Check(aurora::ComputeLayout(0, 0, 10, 10, -1, 2, 1).width == 0, "invalid image");
    Check(aurora::ComputeLayout(0, 0, 10, 10, 2, 2, nan).width == 0, "NaN layout rejected");
    Check(aurora::ComputeLayout(0, 0, 10, 10, 2, 2, infinity).width == 0, "infinite layout rejected");
    Check(aurora::ComputeLayout(0, 0, 10, 10, std::numeric_limits<int>::max(), 2, 3).width == 0,
          "scaled integer overflow rejected");
    Check(aurora::ComputeLayout(std::numeric_limits<int>::max(), 0, 100, 100, 2, 2, 1).width == 0,
          "screen coordinate overflow rejected");
}

void TestPixels()
{
    const std::uint32_t pixels[] = {0xffff0000u, 0xff00ff00u, 0xff0000ffu, 0x00000000u};
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, 0, 0) == 0xffff0000u, "top-left red retains channel order");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, 0, 1) == 0xff0000ffu, "top-down orientation retained");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, 1, 1) == 0, "transparent source");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, 0.5f, 0.5f) == 0xbf404040u, "four neighbors interpolate alpha and color");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, -20, -20) == pixels[0], "negative coordinate clamps");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, 20, 0) == pixels[1], "right edge clamps");
    const std::uint32_t translucent[] = {0x80800000u, 0};
    Check(aurora::SampleBilinearPremultiplied(translucent, 2, 1, 0.5f, 0) == 0x40400000u,
          "premultiplied translucent edge avoids a second alpha multiplication");
    Check(aurora::SampleBilinearPremultiplied(pixels, 1, 1, 10, 20) == pixels[0], "one-pixel image");
    Check(aurora::SampleBilinearPremultiplied(nullptr, 2, 2, 0, 0) == 0, "null buffer rejected");
    Check(aurora::SampleBilinearPremultiplied(pixels, 0, 2, 0, 0) == 0, "invalid dimensions rejected");
    Check(aurora::SampleBilinearPremultiplied(pixels, 2, 2, std::numeric_limits<float>::quiet_NaN(), 0) == 0,
          "nonfinite sample rejected");
}
} // namespace

int main()
{
    TestConfiguration();
    TestLayout();
    TestPixels();
    std::cout << "PASS: " << checks << " portable renderer checks\n";
}
