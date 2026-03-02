import sys


class Tee:    
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()

    def isatty(self) -> bool:
        return False


class LogContext:    
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.log_file = None
        self._orig_out = None
        self._orig_err = None

    def __enter__(self):
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        self._orig_out = sys.stdout
        self._orig_err = sys.stderr
        sys.stdout = Tee(sys.__stdout__, self.log_file)
        sys.stderr = Tee(sys.__stderr__, self.log_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._orig_out
        sys.stderr = self._orig_err
        if self.log_file:
            self.log_file.close()
        return False