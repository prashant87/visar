# wait until fullscreen app launches
sleep 10

# program the FPGA's distoriton data
python /home/ubuntu/src/device_scripts/write_hex.py /home/ubuntu/src/device_scripts/out.hex
