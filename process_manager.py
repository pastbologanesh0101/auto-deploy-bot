"""A tiny process-manager abstraction.

Tracks a single managed process via a PID file so start/stop/is_running
work without relying on systemd, supervisord, or any other real system
service manager. This makes the deployment bot fully testable using
ordinary subprocesses (e.g. `sleep`, a test script, or a real app).
"""
import os
import signal
import subprocess
import time


class ProcessManager:
    def __init__(self, pid_file):
        self.pid_file = pid_file
        # A handle to the Popen object, kept only when *this* instance is
        # the one that started the process. This lets is_running() use
        # proc.poll() (exact, race-free) instead of re-checking a raw PID,
        # which can be misled by PID reuse if the process already exited.
        self._process = None

    def start(self, command):
        """Start `command` (str -> run via shell, list -> run directly).

        Returns the PID of the started process. If something is already
        tracked as running, returns its PID instead of starting a duplicate.
        """
        if self.is_running():
            return self._read_pid()

        proc = subprocess.Popen(
            command,
            shell=isinstance(command, str),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._process = proc
        with open(self.pid_file, "w") as f:
            f.write(str(proc.pid))
        return proc.pid

    def stop(self, timeout=5):
        """Stop the tracked process (SIGTERM, then SIGKILL after timeout).

        Returns True if a process was found and stopped, False if nothing
        was tracked as running.
        """
        pid = self._read_pid()
        if pid is None:
            return False

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._process = None
            self._clear_pid()
            return False

        if self._process is not None:
            # We hold the Popen handle: wait()/kill() properly reap it
            # instead of just polling the raw PID.
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
                try:
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    pass
        else:
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not self._pid_alive(pid):
                    break
                time.sleep(0.1)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        self._process = None
        self._clear_pid()
        return True

    def is_running(self):
        # If this instance started the process, poll() is authoritative and
        # avoids any risk of a since-reused PID being mistaken for it.
        if self._process is not None:
            return self._process.poll() is None

        pid = self._read_pid()
        if pid is None:
            return False
        return self._pid_alive(pid)

    def _read_pid(self):
        if not os.path.exists(self.pid_file):
            return None
        try:
            with open(self.pid_file) as f:
                content = f.read().strip()
            return int(content) if content else None
        except (ValueError, OSError):
            return None

    def _pid_alive(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _clear_pid(self):
        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except OSError:
                pass
