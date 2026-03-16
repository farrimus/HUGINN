#include "http_client.h"
#include "config.h"
#include <windows.h>
#include <winhttp.h>
#include <string>
#include <functional>
#include <nlohmann/json.hpp>

namespace http {

bool postChat(
    const std::string& jsonBody,
    std::function<void(const std::string& chunk)> onChunk,
    std::function<void()> onDone,
    std::string& errorOut)
{
    HINTERNET hSession = WinHttpOpen(
        L"EVEFrontierOverlay/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0);
    if (!hSession) {
        errorOut = "WinHttpOpen failed";
        return false;
    }

    HINTERNET hConnect = WinHttpConnect(
        hSession,
        config::SERVER_HOST_W,
        static_cast<INTERNET_PORT>(config::SERVER_PORT),
        0);
    if (!hConnect) {
        errorOut = "WinHttpConnect failed";
        WinHttpCloseHandle(hSession);
        return false;
    }

    // Convert CHAT_PATH to wide string
    int pathLen = MultiByteToWideChar(CP_UTF8, 0, config::CHAT_PATH, -1, nullptr, 0);
    std::wstring wPath(pathLen, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, config::CHAT_PATH, -1, wPath.data(), pathLen);

    HINTERNET hRequest = WinHttpOpenRequest(
        hConnect,
        L"POST",
        wPath.c_str(),
        nullptr,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        0);  // no HTTPS flag — plain HTTP to VPS
    if (!hRequest) {
        errorOut = "WinHttpOpenRequest failed";
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    // Build token header: "X-Server-Token: <token>"
    std::string tokenHeaderStr = std::string("X-Server-Token: ") + config::SERVER_TOKEN;
    int tokLen = MultiByteToWideChar(CP_UTF8, 0, tokenHeaderStr.c_str(), -1, nullptr, 0);
    std::wstring wTokenHeader(tokLen, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, tokenHeaderStr.c_str(), -1, wTokenHeader.data(), tokLen);

    WinHttpAddRequestHeaders(hRequest,
        L"Content-Type: application/json\r\nAccept: text/event-stream\r\n",
        (DWORD)-1L,
        WINHTTP_ADDREQ_FLAG_ADD);
    WinHttpAddRequestHeaders(hRequest,
        wTokenHeader.c_str(),
        (DWORD)-1L,
        WINHTTP_ADDREQ_FLAG_ADD);

    DWORD bodyLen = static_cast<DWORD>(jsonBody.size());
    BOOL sent = WinHttpSendRequest(
        hRequest,
        WINHTTP_NO_ADDITIONAL_HEADERS, 0,
        WINHTTP_NO_REQUEST_DATA, 0,
        bodyLen, 0);
    if (!sent) {
        errorOut = "WinHttpSendRequest failed";
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    DWORD written = 0;
    WinHttpWriteData(hRequest,
        jsonBody.c_str(), bodyLen, &written);

    if (!WinHttpReceiveResponse(hRequest, nullptr)) {
        errorOut = "WinHttpReceiveResponse failed";
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    // SSE line buffer — handles partial reads across WinHttpReadData calls
    std::string lineBuf;
    bool result = true;

    while (true) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &available) || available == 0)
            break;

        std::string chunk(available, '\0');
        DWORD read = 0;
        if (!WinHttpReadData(hRequest, chunk.data(), available, &read) || read == 0)
            break;
        chunk.resize(read);
        lineBuf += chunk;

        // Process complete lines
        size_t pos = 0;
        while (true) {
            size_t nl = lineBuf.find('\n', pos);
            if (nl == std::string::npos)
                break;

            std::string line = lineBuf.substr(pos, nl - pos);
            // Strip trailing \r if present
            if (!line.empty() && line.back() == '\r')
                line.pop_back();

            pos = nl + 1;

            if (line.rfind("data: ", 0) != 0)
                continue;

            std::string data = line.substr(6);  // after "data: "

            if (data == "[DONE]") {
                onDone();
                goto done;
            }

            if (!data.empty() && data.front() == '{') {
                try {
                    auto j = nlohmann::json::parse(data);
                    if (j.contains("error")) {
                        errorOut = j["error"].get<std::string>();
                        result = false;
                        goto done;
                    }
                    if (j.contains("text")) {
                        onChunk(j["text"].get<std::string>());
                    }
                } catch (...) {
                    // Malformed JSON — skip line
                }
            }
        }

        // Keep unprocessed remainder in buffer
        lineBuf = lineBuf.substr(pos);
    }

done:
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    return result;
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

static bool _openHandles(const std::string& method, const std::string& path,
                         HINTERNET& hSession, HINTERNET& hConnect,
                         HINTERNET& hRequest, std::string& errorOut)
{
    hSession = WinHttpOpen(L"EVEFrontierOverlay/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) { errorOut = "WinHttpOpen failed"; return false; }

    hConnect = WinHttpConnect(hSession, config::SERVER_HOST_W,
        static_cast<INTERNET_PORT>(config::SERVER_PORT), 0);
    if (!hConnect) {
        WinHttpCloseHandle(hSession);
        errorOut = "WinHttpConnect failed"; return false;
    }

    int wLen = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
    std::wstring wPath(wLen, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wPath.data(), wLen);

    int mLen = MultiByteToWideChar(CP_UTF8, 0, method.c_str(), -1, nullptr, 0);
    std::wstring wMethod(mLen, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, method.c_str(), -1, wMethod.data(), mLen);

    hRequest = WinHttpOpenRequest(hConnect, wMethod.c_str(), wPath.c_str(),
        nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!hRequest) {
        WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession);
        errorOut = "WinHttpOpenRequest failed"; return false;
    }

    std::string tokenHdr = std::string("X-Server-Token: ") + config::SERVER_TOKEN;
    int tLen = MultiByteToWideChar(CP_UTF8, 0, tokenHdr.c_str(), -1, nullptr, 0);
    std::wstring wToken(tLen, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, tokenHdr.c_str(), -1, wToken.data(), tLen);
    WinHttpAddRequestHeaders(hRequest, wToken.c_str(), (DWORD)-1L, WINHTTP_ADDREQ_FLAG_ADD);

    return true;
}

static void _closeHandles(HINTERNET hRequest, HINTERNET hConnect, HINTERNET hSession)
{
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
}

bool getJson(const std::string& path, std::string& bodyOut, std::string& errorOut)
{
    HINTERNET hSession = nullptr, hConnect = nullptr, hRequest = nullptr;
    if (!_openHandles("GET", path, hSession, hConnect, hRequest, errorOut))
        return false;

    WinHttpAddRequestHeaders(hRequest, L"Accept: application/json\r\n",
        (DWORD)-1L, WINHTTP_ADDREQ_FLAG_ADD);

    if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
            WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
        errorOut = "WinHttpSendRequest failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }

    if (!WinHttpReceiveResponse(hRequest, nullptr)) {
        errorOut = "WinHttpReceiveResponse failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }

    bodyOut.clear();
    while (true) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &available) || available == 0)
            break;
        std::string chunk(available, '\0');
        DWORD read = 0;
        if (!WinHttpReadData(hRequest, chunk.data(), available, &read) || read == 0)
            break;
        chunk.resize(read);
        bodyOut += chunk;
    }

    _closeHandles(hRequest, hConnect, hSession);
    return true;
}

bool postEmpty(const std::string& path, std::string& errorOut)
{
    HINTERNET hSession = nullptr, hConnect = nullptr, hRequest = nullptr;
    if (!_openHandles("POST", path, hSession, hConnect, hRequest, errorOut))
        return false;

    WinHttpAddRequestHeaders(hRequest, L"Content-Length: 0\r\n",
        (DWORD)-1L, WINHTTP_ADDREQ_FLAG_ADD);

    if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
            WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
        errorOut = "WinHttpSendRequest failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }

    if (!WinHttpReceiveResponse(hRequest, nullptr)) {
        errorOut = "WinHttpReceiveResponse failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }

    _closeHandles(hRequest, hConnect, hSession);
    return true;
}

bool postJson(const std::string& path, const std::string& jsonBody,
              std::string& bodyOut, std::string& errorOut)
{
    HINTERNET hSession = nullptr, hConnect = nullptr, hRequest = nullptr;
    if (!_openHandles("POST", path, hSession, hConnect, hRequest, errorOut))
        return false;

    WinHttpAddRequestHeaders(hRequest,
        L"Content-Type: application/json\r\nAccept: application/json\r\n",
        (DWORD)-1L, WINHTTP_ADDREQ_FLAG_ADD);

    DWORD bodyLen = static_cast<DWORD>(jsonBody.size());
    if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
            WINHTTP_NO_REQUEST_DATA, 0, bodyLen, 0)) {
        errorOut = "WinHttpSendRequest failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }
    DWORD written = 0;
    WinHttpWriteData(hRequest, jsonBody.c_str(), bodyLen, &written);

    if (!WinHttpReceiveResponse(hRequest, nullptr)) {
        errorOut = "WinHttpReceiveResponse failed";
        _closeHandles(hRequest, hConnect, hSession);
        return false;
    }

    bodyOut.clear();
    while (true) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &available) || available == 0)
            break;
        std::string chunk(available, '\0');
        DWORD read = 0;
        if (!WinHttpReadData(hRequest, chunk.data(), available, &read) || read == 0)
            break;
        chunk.resize(read);
        bodyOut += chunk;
    }
    _closeHandles(hRequest, hConnect, hSession);
    return true;
}

}  // namespace http
