#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <shlwapi.h>
#include <cstdio>
#include <cwchar>
#include <string>
#include <vector>
#pragma comment(lib, "shlwapi.lib")

static void printError(const char* context, DWORD err) {
    char buf[512]{};
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                   nullptr, err, 0, buf, sizeof(buf), nullptr);
    fprintf(stderr, "[injector] %s failed (0x%08X): %s\n", context, err, buf);
}

static std::vector<DWORD> findProcessIds(const wchar_t* targetName) {
    std::vector<DWORD> pids;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) {
        printError("CreateToolhelp32Snapshot", GetLastError());
        return pids;
    }

    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof(entry);

    if (Process32FirstW(snap, &entry)) {
        do {
            // Case-insensitive match
            if (_wcsicmp(entry.szExeFile, targetName) == 0) {
                pids.push_back(entry.th32ProcessID);
            }
        } while (Process32NextW(snap, &entry));
    }

    CloseHandle(snap);
    return pids;
}

int wmain(int argc, wchar_t* argv[]) {
    if (argc < 2) {
        fwprintf(stderr,
            L"Usage: injector.exe <dll_path> [process_name]\n"
            L"  dll_path     Absolute path to overlay.dll\n"
            L"  process_name Target process (default: exefile.exe)\n");
        return 1;
    }

    const wchar_t* dllPath     = argv[1];
    const wchar_t* processName = (argc >= 3) ? argv[2] : L"exefile.exe";

    // Verify DLL path is absolute
    if (PathIsRelativeW(dllPath)) {
        fwprintf(stderr, L"[injector] DLL path must be absolute: %ls\n", dllPath);
        return 1;
    }

    // Find target process(es)
    auto pids = findProcessIds(processName);
    if (pids.empty()) {
        fwprintf(stderr, L"[injector] No process named '%ls' found.\n", processName);
        return 1;
    }
    if (pids.size() > 1) {
        fwprintf(stderr, L"[injector] Multiple processes named '%ls' found (%zu). Aborting.\n",
                 processName, pids.size());
        return 1;
    }

    DWORD pid = pids[0];
    wprintf(L"[injector] Target PID: %lu  DLL: %ls\n", pid, dllPath);

    // Open process
    HANDLE hProcess = OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
        FALSE, pid);
    if (!hProcess) {
        printError("OpenProcess", GetLastError());
        return 1;
    }

    // Allocate remote memory for DLL path string (wide chars)
    size_t pathBytes = (wcslen(dllPath) + 1) * sizeof(wchar_t);
    LPVOID remotePath = VirtualAllocEx(hProcess, nullptr, pathBytes,
                                       MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remotePath) {
        printError("VirtualAllocEx", GetLastError());
        CloseHandle(hProcess);
        return 1;
    }

    // Write DLL path into remote process
    SIZE_T written = 0;
    if (!WriteProcessMemory(hProcess, remotePath, dllPath, pathBytes, &written)
        || written != pathBytes) {
        printError("WriteProcessMemory", GetLastError());
        VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    // Get LoadLibraryW address in kernel32
    LPVOID loadLibAddr = reinterpret_cast<LPVOID>(
        GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW"));
    if (!loadLibAddr) {
        printError("GetProcAddress(LoadLibraryW)", GetLastError());
        VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    // Create remote thread that calls LoadLibraryW(dllPath)
    HANDLE hThread = CreateRemoteThread(hProcess, nullptr, 0,
        reinterpret_cast<LPTHREAD_START_ROUTINE>(loadLibAddr),
        remotePath, 0, nullptr);
    if (!hThread) {
        printError("CreateRemoteThread", GetLastError());
        VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    // Wait for LoadLibrary to complete
    DWORD waitResult = WaitForSingleObject(hThread, 10000);
    if (waitResult != WAIT_OBJECT_0) {
        fprintf(stderr, "[injector] WaitForSingleObject timed out or failed: %lu\n", waitResult);
        CloseHandle(hThread);
        VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    DWORD exitCode = 0;
    GetExitCodeThread(hThread, &exitCode);

    if (exitCode == 0) {
        fprintf(stderr, "[injector] LoadLibraryW returned NULL — DLL load failed.\n"
                        "           Check DLL path, dependencies, and that it is an x64 binary.\n");
        CloseHandle(hThread);
        VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    wprintf(L"[injector] Injection successful. Module base: 0x%08X\n", exitCode);

    // Cleanup
    CloseHandle(hThread);
    VirtualFreeEx(hProcess, remotePath, 0, MEM_RELEASE);
    CloseHandle(hProcess);
    return 0;
}
