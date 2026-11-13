"""Own a child before it runs; verify cleanup independently of parent exit."""

import ctypes
import math
import os
import signal
import subprocess
import time


def remaining(deadline):
    return max(0.0, deadline-time.monotonic())


class WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w

        class Limits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", w.DWORD), ("minimum_ws", ctypes.c_size_t),
                ("maximum_ws", ctypes.c_size_t), ("active_limit", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", Limits), ("io", ctypes.c_ulonglong*6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [("times", ctypes.c_longlong*4), ("page_faults", w.DWORD),
                        ("total", w.DWORD), ("active", w.DWORD), ("terminated", w.DWORD)]

        class Thread(ctypes.Structure):
            _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("id", w.DWORD),
                        ("owner", w.DWORD), ("priority", w.LONG), ("delta", w.LONG), ("flags", w.DWORD)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD,
                                          ctypes.c_void_p], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "GetProcessTimes": ([w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.c_void_p, ctypes.c_void_p], w.BOOL),
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Thread32First": ([w.HANDLE, ctypes.POINTER(Thread)], w.BOOL),
            "Thread32Next": ([w.HANDLE, ctypes.POINTER(Thread)], w.BOOL),
            "OpenThread": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "GetProcessIdOfThread": ([w.HANDLE], w.DWORD),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.Accounting, self.Thread = Accounting, Thread
        self.handle = self.check(self.api.CreateJobObjectW(None, None))
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
            self.check(self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                        ctypes.sizeof(limits)))
        except BaseException:
            self.close()
            raise

    @staticmethod
    def check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def attach(self, pid):
        process = self.check(self.api.OpenProcess(0x1101, False, pid))
        try:
            stamps = [ctypes.c_ulonglong() for _ in range(4)]
            self.check(self.api.GetProcessTimes(process, *(ctypes.byref(stamp) for stamp in stamps)))
            self.check(self.api.AssignProcessToJobObject(self.handle, process))
            return stamps[0].value
        finally:
            self.check(self.api.CloseHandle(process))

    def resume(self, pid):
        # CREATE_SUSPENDED prevents descendants before assignment to the job.
        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            thread, matches = self.Thread(), []
            thread.size = ctypes.sizeof(thread)
            found = self.api.Thread32First(snapshot, ctypes.byref(thread))
            while found:
                if thread.owner == pid:
                    matches.append(thread.id)
                found = self.api.Thread32Next(snapshot, ctypes.byref(thread))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
            if len(matches) != 1:
                raise RuntimeError("Cannot identify the suspended CLI's unique initial thread")
            handle = self.check(self.api.OpenThread(0x42, False, matches[0]))
            try:
                if self.api.GetProcessIdOfThread(handle) != pid:
                    raise RuntimeError("Initial thread no longer belongs to the owned CLI")
                previous = self.api.ResumeThread(handle)
                if previous == 0xffffffff:
                    raise ctypes.WinError(ctypes.get_last_error())
                if previous != 1:
                    raise RuntimeError("Unexpected CLI initial-thread suspension state")
            finally:
                self.check(self.api.CloseHandle(handle))
        finally:
            self.check(self.api.CloseHandle(snapshot))

    def active(self):
        counts = self.Accounting()
        self.check(self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(counts),
                                                     ctypes.sizeof(counts), None))
        return counts.active

    def terminate(self):
        self.check(self.api.TerminateJobObject(self.handle, 1))

    def close(self):
        if self.handle is not None:
            self.check(self.api.CloseHandle(self.handle))
            self.handle = None


class OwnedProcess:
    def __init__(self):
        self.process = None
        self.job = WindowsJob() if os.name == "nt" else None
        self.attached = False
        self.created = None

    def start(self, command, **arguments):
        if self.process is not None:
            raise RuntimeError("Process owner cannot be reused")
        flags = {"creationflags": 4} if self.job else {"start_new_session": True}
        self.process = subprocess.Popen(command, **arguments, **flags)
        if self.job:
            self.created = self.job.attach(self.process.pid)
            self.attached = True
            self.job.resume(self.process.pid)
        return self.process

    def identity(self):
        return {"pid": self.process.pid if self.process else None,
                "containment": "windows_job" if self.job else "posix_process_group",
                "created_filetime": self.created}

    def stop(self, timeout=10):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Cleanup timeout must be finite and positive")
        started = time.monotonic()
        deadline = started+timeout
        process, active = self.process, 0
        if process is not None:
            if self.job and self.attached:
                active = self.job.active()
                if active:
                    self.job.terminate()
                while self.job.active():
                    if not remaining(deadline):
                        raise subprocess.TimeoutExpired("owned Windows job cleanup", timeout)
                    time.sleep(min(.02, remaining(deadline)))
            elif self.job:
                # Assignment failed: the initial thread has never been resumed.
                active = int(process.poll() is None)
                if active:
                    process.kill()
            else:
                active = self._group_active()
                if active:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=min(3, remaining(deadline)))
                    except subprocess.TimeoutExpired:
                        pass
                    if self._group_active():
                        os.killpg(process.pid, signal.SIGKILL)
                    while self._group_active():
                        process.poll()
                        if not remaining(deadline):
                            raise subprocess.TimeoutExpired("owned process-group cleanup", timeout)
                        time.sleep(min(.02, remaining(deadline)))
            process.wait(timeout=remaining(deadline))
        return {"status": "verified", **self.identity(), "active_before": active,
                "active_after": 0, "elapsed_seconds": time.monotonic()-started}

    def _group_active(self):
        try:
            os.killpg(self.process.pid, 0)
        except ProcessLookupError:
            return False
        return True

    def close(self):
        if self.job:
            self.job.close()
