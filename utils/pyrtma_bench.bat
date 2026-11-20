@echo off
rem The standard benchmark suite: one publisher with 0, 1 and 5 subscribers, at
rem 128, 1024 and 8192 bytes, 5 runs each. Extra arguments go to every run,
rem such as --start-manager, or -s HOST:PORT for a manager that is running.
echo pyrtma benchmark suite
echo.
for %%n in (0 1 5) do (
    for %%s in (128 1024 8192) do (
        python "%~dp0pyrtma_bench.py" -n 10000 -np 1 -ns %%n -ms %%s -r 5 %*
        echo.
    )
)
