import socket
import threading
import time
import struct
import subprocess
import sys
import copy

# Shared timestamp with thread-safe access
current_timestamp = 0.0
timestamp_lock = threading.Lock()

# Device management
devices = {}
devices_lock = threading.Lock()

def timestamp_updater():
    """Update global timestamp from ROS listener subprocess"""
    global current_timestamp
    
    process = subprocess.Popen(
        ['python3', '-u', 'listener_time.py'],
        stdout=subprocess.PIPE,
        text=True,
        bufsize=0
    )
    
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            try:
                new_ts = float(line.strip())
                with timestamp_lock:
                    current_timestamp = new_ts
                #print(f"Updated timestamp to: {new_ts}")
                
            except ValueError:
                print(f"Invalid timestamp received: {line}")
                
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        process.wait()

# def timestamp_updater():
#     global current_timestamp

#     while True:
#         try:
#             current_timestamp = time.time()
#             time.sleep(0.01)
#         except Exception as e:
#             print(f"Error updating timestamp: {e}")

def handle_device(device_name, addr, sock):
    """Handle device synchronization with ROS-based timestamps"""
    start_time = time.time()
    duration = 8
    end_time = start_time + duration
    interval = 0.1  # 100ms

    try:
        while time.time() < end_time:
            with timestamp_lock:
                ts = current_timestamp
            
            data = struct.pack('d', ts)
            sock.sendto(data, addr)
            time.sleep(interval)

        sock.sendto(b"Stop Sync", addr)
        print(f"Sent stop command to {device_name} at {addr}")

        with devices_lock:
            devices[device_name]['status'] = 'synced'

        with devices_lock:
            all_synced = all(device['status'] == 'synced' for device in devices.values())

        if all_synced:
            with timestamp_lock:
                final_ts = current_timestamp
            with open('sync_completion.txt', 'w') as f:
                f.write(str(final_ts))
            print(f"All devices synced at ROS time: {final_ts}")

    except Exception as e:
        print(f"Error handling {device_name}: {e}")

def command_listener(sock):
    """Handle console input for collection control"""
    print("\nEnter commands:")
    print("  'begin' - Start collection for all synced devices")
    print("  'end'   - Stop collection for all devices")
    print("  'exit'   - Shutdown server\n")
    
    while True:
        try:
            cmd = input("> ").strip().lower()
            
            if cmd == "begin":
                with devices_lock:
                    # Check synchronization status
                    all_synced = all(device['status'] == 'synced' for device in devices.values())
                    if not all_synced:
                        print("Error: Not all devices are synced!")
                        continue
                    
                    names = list(devices.keys())
                    print("names: ", names)
                    device_names = copy.deepcopy(names)
                    
                    if 'SensorCollector' in device_names:
                        device_names.remove('SensorCollector')
                    print("device_names: ", device_names)
                    msg = f"Start Collection: {device_names}"
                    sock.sendto(msg.encode('utf-8'), ("0.0.0.0", 10000))
                    msg = f"Start Collection"
                    if 'SensorCollector' in names:
                        sock.sendto(msg.encode('utf-8'), (devices['SensorCollector']['addr'][0], 11111))

                    
                    # Record start timestamp
                    with timestamp_lock:
                        start_ts = current_timestamp
                    with open('collection_start.txt', 'w') as f:
                        f.write(str(start_ts))
                    print(f"Collection started at {start_ts}")

            elif cmd == "end":
                with devices_lock:
                    # Send stop command to all devices
                    for name, info in devices.items():
                        sock.sendto(b"Stop Collection", info['addr'])
                        print(f"Sent stop command to {name}")
                    
                    msg = f"End Collection"
                    sock.sendto(msg.encode('utf-8'), ("0.0.0.0", 10000))
                    if 'SensorCollector' in names:
                        msg = f"End Collection"
                        sock.sendto(msg.encode('utf-8'), (devices['SensorCollector']['addr'][0], 11111))

                    # Record end timestamp
                    with timestamp_lock:
                        end_ts = current_timestamp
                    with open('collection_end.txt', 'w') as f:
                        f.write(str(end_ts))
                    print(f"Collection stopped at {end_ts}")

            elif cmd == "exit":
                print("Shutting down server...")
                sys.exit(0)

            else:
                print("Unknown command. Valid commands: begin, end, exit")

        except Exception as e:
            print(f"Command processing error: {e}")

def main():
    host = '0.0.0.0'
    port = 6666

    # Start ROS timestamp updater
    ros_thread = threading.Thread(target=timestamp_updater, daemon=True)
    ros_thread.start()

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))

    # Start command listener in main thread
    command_thread = threading.Thread(
        target=command_listener,
        args=(sock,),
        daemon=True
    )
    command_thread.start()

    print(f"ROS Sync server listening on {host}:{port}")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            decoded = data.decode().strip()
            device_name, device_ip = decoded.split(':')
            
            with devices_lock:
                if device_name in devices:
                    print(f"Device {device_name} connected before, retry to sync")
                    # continue 

                devices[device_name] = {
                    'status': 'syncing',
                    'ip': device_ip,
                    'addr': (device_ip,8888)
                }

            threading.Thread(
                target=handle_device,
                args=(device_name, (device_ip,8888), sock)
            ).start()
            print(f"Started sync for {device_name} at {device_ip}")

        except ValueError:
            print(f"Invalid message format from {addr}: {data}")
        except Exception as e:
            print(f"Error receiving data: {e}")

if __name__ == '__main__':
    main()