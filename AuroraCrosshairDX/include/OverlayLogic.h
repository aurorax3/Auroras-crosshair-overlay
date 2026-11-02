#pragma once

// Platform-independent configuration, layout and pixel operations used by the
// Win32 overlay. Keeping these independent of HWND/GDI makes the invariants
// testable without a running desktop or graphics device.
#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <string_view>
#include <utility>

namespace aurora {

struct Settings {
    float scale = 1.0f;
    std::string crosshair = "dots/osupink.png";
};

inline bool IsValidUtf8(std::string_view bytes)
{
    for (std::size_t i = 0; i < bytes.size();) {
        const auto lead = static_cast<unsigned char>(bytes[i++]);
        if (lead < 0x80)
            continue;
        unsigned count = 0;
        std::uint32_t codepoint = 0;
        std::uint32_t minimum = 0;
        if (lead >= 0xc2 && lead <= 0xdf) {
            count = 1; codepoint = lead & 0x1f; minimum = 0x80;
        } else if (lead >= 0xe0 && lead <= 0xef) {
            count = 2; codepoint = lead & 0x0f; minimum = 0x800;
        } else if (lead >= 0xf0 && lead <= 0xf4) {
            count = 3; codepoint = lead & 0x07; minimum = 0x10000;
        } else {
            return false;
        }
        if (count > bytes.size() - i)
            return false;
        for (unsigned n = 0; n < count; ++n) {
            const auto next = static_cast<unsigned char>(bytes[i++]);
            if ((next & 0xc0) != 0x80)
                return false;
            codepoint = (codepoint << 6) | (next & 0x3f);
        }
        if (codepoint < minimum || codepoint > 0x10ffff ||
            (codepoint >= 0xd800 && codepoint <= 0xdfff))
            return false;
    }
    return true;
}

inline std::string_view TrimConfigWhitespace(std::string_view text)
{
    while (!text.empty() && (text.front() == ' ' || text.front() == '\t'))
        text.remove_prefix(1);
    while (!text.empty() && (text.back() == ' ' || text.back() == '\t'))
        text.remove_suffix(1);
    return text;
}

// Call only after UTF-8 validation. Count Unicode scalar values rather than
// bytes so the limit agrees with the Python controller for non-ASCII names.
inline std::size_t Utf8Length(std::string_view text)
{
    std::size_t length = 0;
    for (const unsigned char byte : text) {
        if ((byte & 0xc0) != 0x80)
            ++length;
    }
    return length;
}

inline bool NormalizeCrosshairPath(std::string_view value, std::string& normalized)
{
    if (value.empty() || !IsValidUtf8(value) || Utf8Length(value) > 4096 ||
        value.front() == '/' || value.front() == '\\')
        return false;
    std::string candidate(value);
    for (char& ch : candidate) {
        const auto byte = static_cast<unsigned char>(ch);
        if (byte < 0x20 || byte == 0x7f || ch == ':' || ch == '<' || ch == '>' ||
            ch == '"' || ch == '|' || ch == '?' || ch == '*')
            return false;
        if (ch == '\\')
            ch = '/';
    }
    std::size_t begin = 0;
    for (;;) {
        const auto end = candidate.find('/', begin);
        const auto part = std::string_view(candidate).substr(
            begin, end == std::string::npos ? end : end - begin);
        if (part.empty() || Utf8Length(part) > 255 || part == "." || part == ".." ||
            part.back() == ' ' || part.back() == '.')
            return false;
        if (end == std::string::npos)
            break;
        begin = end + 1;
    }
    normalized = std::move(candidate);
    return true;
}

inline bool ParseSettings(const std::string& bytes, Settings& output)
{
    constexpr std::size_t maxConfigurationBytes = 64 * 1024;
    if (bytes.size() > maxConfigurationBytes || !IsValidUtf8(bytes))
        return false;
    for (const unsigned char byte : bytes) {
        if ((byte < 0x20 && byte != '\t' && byte != '\r' && byte != '\n') || byte == 0x7f)
            return false;
    }

    std::string_view input(bytes);
    if (input.substr(0, 3) == "\xef\xbb\xbf")
        input.remove_prefix(3);
    // Manual configuration files historically allowed either key on its own.
    // Apply recognized values to a copy so malformed updates cannot partially
    // modify live state, while omitted fields retain their current values.
    Settings candidate = output;
    bool sawScale = false;
    bool sawCrosshair = false;
    while (!input.empty()) {
        const auto newline = input.find('\n');
        auto line = input.substr(0, newline);
        if (newline == std::string_view::npos)
            input = {};
        else
            input.remove_prefix(newline + 1);
        if (!line.empty() && line.back() == '\r')
            line.remove_suffix(1);
        line = TrimConfigWhitespace(line);
        if (line.empty() || line.front() == '#' || line.front() == ';')
            continue;
        const auto equals = line.find('=');
        if (equals == std::string_view::npos)
            return false;
        const auto key = TrimConfigWhitespace(line.substr(0, equals));
        auto value = TrimConfigWhitespace(line.substr(equals + 1));
        if (key.empty() || value.empty() || key.find_first_of(" \t\r") != std::string_view::npos)
            return false;
        if (key == "scale") {
            if (sawScale)
                return false;
            sawScale = true;
            if (value.front() == '+') {
                value.remove_prefix(1);
                if (!value.empty() && (value.front() == '+' || value.front() == '-'))
                    return false;
            }
            if (value.empty())
                return false;
            double scale = 0.0;
            const auto result = std::from_chars(value.data(), value.data() + value.size(), scale);
            if (result.ec != std::errc{} || result.ptr != value.data() + value.size() ||
                !std::isfinite(scale))
                return false;
            candidate.scale = static_cast<float>(std::clamp(scale, 0.5, 3.0));
        } else if (key == "crosshair") {
            if (sawCrosshair || !NormalizeCrosshairPath(value, candidate.crosshair))
                return false;
            sawCrosshair = true;
        }
        // Well-formed unknown keys are ignored for forward compatibility.
    }
    if (!sawScale && !sawCrosshair)
        return false;
    output = std::move(candidate);
    return true;
}

struct Layout {
    int left = 0;
    int top = 0;
    int width = 0;
    int height = 0;
    int sourceX = 0;
    int sourceY = 0;
    int scaledWidth = 0;
    int scaledHeight = 0;
};

inline Layout ComputeLayout(int monitorLeft, int monitorTop, int monitorWidth, int monitorHeight,
                            int imageWidth, int imageHeight, float scale)
{
    if (monitorWidth <= 0 || monitorHeight <= 0 || imageWidth <= 0 || imageHeight <= 0 ||
        !std::isfinite(scale) || scale <= 0.0f)
        return {};
    const double width = std::floor(static_cast<double>(imageWidth) * scale);
    const double height = std::floor(static_cast<double>(imageHeight) * scale);
    if (width > std::numeric_limits<int>::max() || height > std::numeric_limits<int>::max())
        return {};
    const int scaledWidth = std::max(1, static_cast<int>(width));
    const int scaledHeight = std::max(1, static_cast<int>(height));
    const std::int64_t imageLeft = static_cast<std::int64_t>(monitorLeft) + monitorWidth / 2 - scaledWidth / 2;
    const std::int64_t imageTop = static_cast<std::int64_t>(monitorTop) + monitorHeight / 2 - scaledHeight / 2;
    const auto left = std::max<std::int64_t>(monitorLeft, imageLeft);
    const auto top = std::max<std::int64_t>(monitorTop, imageTop);
    const auto right = std::min(static_cast<std::int64_t>(monitorLeft) + monitorWidth, imageLeft + scaledWidth);
    const auto bottom = std::min(static_cast<std::int64_t>(monitorTop) + monitorHeight, imageTop + scaledHeight);
    if (left < std::numeric_limits<int>::min() || left > std::numeric_limits<int>::max() ||
        top < std::numeric_limits<int>::min() || top > std::numeric_limits<int>::max())
        return {};
    return {static_cast<int>(left), static_cast<int>(top), static_cast<int>(right - left),
            static_cast<int>(bottom - top), static_cast<int>(left - imageLeft),
            static_cast<int>(top - imageTop), scaledWidth, scaledHeight};
}

inline std::uint32_t SampleBilinearPremultiplied(const std::uint32_t* pixels, int width, int height,
                                               float sourceX, float sourceY)
{
    if (!pixels || width <= 0 || height <= 0 || !std::isfinite(sourceX) || !std::isfinite(sourceY))
        return 0;
    const double x = std::clamp(static_cast<double>(sourceX), 0.0, static_cast<double>(width - 1));
    const double y = std::clamp(static_cast<double>(sourceY), 0.0, static_cast<double>(height - 1));
    const int x0 = static_cast<int>(x);
    const int y0 = static_cast<int>(y);
    const int x1 = std::min(x0 + 1, width - 1);
    const int y1 = std::min(y0 + 1, height - 1);
    const double fx = x - x0;
    const double fy = y - y0;
    const auto row0 = static_cast<std::size_t>(y0) * static_cast<std::size_t>(width);
    const auto row1 = static_cast<std::size_t>(y1) * static_cast<std::size_t>(width);
    const std::uint32_t samples[] = {pixels[row0 + x0], pixels[row0 + x1],
                                     pixels[row1 + x0], pixels[row1 + x1]};
    const double weights[] = {(1.0 - fx) * (1.0 - fy), fx * (1.0 - fy), (1.0 - fx) * fy, fx * fy};
    std::uint32_t pixel = 0;
    for (unsigned shift = 0; shift <= 24; shift += 8) {
        double channel = 0.0;
        for (unsigned n = 0; n < 4; ++n)
            channel += ((samples[n] >> shift) & 0xff) * weights[n];
        pixel |= static_cast<std::uint32_t>(std::lround(channel)) << shift;
    }
    return pixel;
}

} // namespace aurora
