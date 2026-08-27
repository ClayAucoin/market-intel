from datetime import datetime
from pathlib import Path
import sys


LOG_DIR = Path("logs")


class TeeOutput:
    def __init__(
        self,
        terminal,
        log_file,
    ):
        self.terminal = terminal
        self.log_file = log_file

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def isatty(self):
        return self.terminal.isatty()


def start_daily_log():
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    log_path = (
        LOG_DIR
        / f"daily_market_intel_{timestamp}.log"
    )

    log_file = log_path.open(
        "w",
        encoding="utf-8",
    )

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = TeeOutput(
        original_stdout,
        log_file,
    )

    sys.stderr = TeeOutput(
        original_stderr,
        log_file,
    )

    return {
        "path": log_path,
        "file": log_file,
        "stdout": original_stdout,
        "stderr": original_stderr,
    }


def stop_daily_log(log):
    sys.stdout = log["stdout"]
    sys.stderr = log["stderr"]

    log["file"].close()