"""
MATLAB bridge for the SSCI toolchain
=====================================
Thin wrapper that calls MATLAB scripts in batch mode from Python, passing
inputs via a JSON file and parsing CSV stdout/file outputs.

Design choice (ARCHITECTURE.md T1): we avoid `matlab.engine.python` (which
requires a separate install per MATLAB version) and instead reuse the
`matlab -batch` pattern already used by the Paper 0 toolchain. The penalty
is a per-call startup overhead of ~10-15 s; this is acceptable for the
SSCI pipeline because the orbital domain is called once per mission and
once per reference (so 2 calls per `ssci_orchestrator.py` run).

Author: Federico Toson
"""
from __future__ import annotations
import csv
import json
import subprocess
import tempfile
from pathlib import Path


# Path to the MATLAB binary. Override via the MATLAB_BIN environment
# variable if installed elsewhere (e.g. on Linux servers).
MATLAB_BIN_DEFAULT = "/Applications/MATLAB_R2026a.app/bin/matlab"


# ----------------------------------------------------------------------- #
def call_matlab(script_path: Path | str,
                inputs: dict,
                matlab_bin: str = MATLAB_BIN_DEFAULT,
                timeout_s: float = 300.0,
                keep_tmp: bool = False) -> dict:
    """Invoke a MATLAB function script with a JSON inputs file.

    Parameters
    ----------
    script_path : Path
        Path to a `.m` script that defines a function with signature
        `function script_name(input_json, output_csv)`. The script must
        write a CSV with a `metric,value` header to `output_csv`.
    inputs : dict
        Python dictionary of mission inputs. Serialised to JSON and
        passed as the first argument to the MATLAB function.
    matlab_bin : str
        Path to the MATLAB binary (defaults to MATLAB_BIN_DEFAULT).
    timeout_s : float
        Maximum wall-clock seconds before the MATLAB call is killed.
    keep_tmp : bool
        If True, the temporary directory with input.json + output.csv
        is preserved (useful for debugging).

    Returns
    -------
    dict[str, float]
        Parsed CSV output, keyed by `metric`.
    """
    script_path = Path(script_path).expanduser().resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"MATLAB script not found: {script_path}")

    tmp_ctx = tempfile.TemporaryDirectory(delete=not keep_tmp)
    td = Path(tmp_ctx.name)
    try:
        input_json = td / "input.json"
        output_csv = td / "output.csv"
        with open(input_json, "w") as f:
            json.dump(inputs, f, indent=2)

        # The -batch flag runs a single MATLAB expression then exits.
        # We escape paths with forward slashes (MATLAB tolerates them on macOS).
        expr = (
            f"{script_path.stem}('{input_json.as_posix()}', "
            f"'{output_csv.as_posix()}')"
        )
        cmd = [matlab_bin, "-nodesktop", "-nosplash", "-batch", expr]

        result = subprocess.run(
            cmd,
            cwd=str(script_path.parent),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"MATLAB call to {script_path.name} failed (rc={result.returncode}).\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        if not output_csv.exists():
            raise RuntimeError(
                f"MATLAB script {script_path.name} returned 0 but did not "
                f"create the expected output CSV at {output_csv}.\n"
                f"stdout:\n{result.stdout}"
            )

        # Parse CSV: expects header `metric,value`
        out: dict[str, float] = {}
        with open(output_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    out[row["metric"]] = float(row["value"])
                except (KeyError, ValueError) as e:
                    raise RuntimeError(
                        f"Malformed CSV row {row}: {e}"
                    ) from e
        return out

    finally:
        if not keep_tmp:
            tmp_ctx.cleanup()


# ----------------------------------------------------------------------- #
def check_matlab_available(matlab_bin: str = MATLAB_BIN_DEFAULT) -> bool:
    """Return True if the MATLAB binary at `matlab_bin` is callable.

    Useful as a precondition in `ssci_orchestrator.py` to fail fast with
    a clear message if MATLAB is missing.
    """
    try:
        result = subprocess.run(
            [matlab_bin, "-batch", "disp('OK')"],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0 and "OK" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
