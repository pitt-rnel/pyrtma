@echo off
echo pyrtma (Native) bench tests:
echo.

echo "1 Producer, No Consumers:"
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 0 -ms 128
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 0 -ms 1024
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 0 -ms 8192
echo.

echo "1 Producer, 1 Consumers:"
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 1 -ms 128
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 1 -ms 1024
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 1 -ms 8192
echo.

echo "1 Producer, 5 Consumers:"
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 5 -ms 128
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 5 -ms 1024
echo.
python pyrtma_bench.py -n 10000 -np 1 -ns 5 -ms 8192
echo.
