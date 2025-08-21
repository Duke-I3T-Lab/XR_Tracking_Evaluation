#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import TransformStamped
from datetime import datetime
import os
import signal
import sys
import socket
import threading

class MultiTrajectoryLogger:
    def __init__(self, object_names=None, output_dir='./vicon_trajectory_logs'):
        self.object_names = object_names or []
        self.output_dir = output_dir
        self.subscribers = []
        self.file_handles = {}
        self.is_collecting = False

        os.makedirs(self.output_dir, exist_ok=True)

    def _setup_files(self):
        self.base_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        for obj in self.object_names:
            filename = f"{obj}_{self.base_timestamp}.csv"
            file_path = os.path.join(self.output_dir, filename)
            try:
                fh = open(file_path, 'a')
                self.file_handles[obj] = fh
                rospy.loginfo(f"Created log file: {file_path}")
            except IOError as e:
                rospy.logerr(f"Error opening file for {obj}: {str(e)}")

    def _callback_factory(self, object_name):
        def callback(data):
            if object_name not in self.file_handles:
                return

            timestamp = data.header.stamp.secs + data.header.stamp.nsecs / 1e9
            t = data.transform.translation
            r = data.transform.rotation
            
            entry = (f"{timestamp} {t.x} {t.y} {t.z} "
                     f"{r.x} {r.y} {r.z} {r.w}\n")
            
            try:
                self.file_handles[object_name].write(entry)
                self.file_handles[object_name].flush()
            except IOError as e:
                rospy.logerr(f"Write error for {object_name}: {str(e)}")

        return callback

    def start(self):
        # if not self.object_names:
        #     rospy.logwarn("No objects to track. Not starting.")
        #     return
        # if not rospy.is_initialized():
        #     rospy.init_node('multi_trajectory_logger', anonymous=True)
        self._setup_files()
        for obj in self.object_names:
            topic = f"/vicon/{obj}/{obj}"
            try:
                callback = self._callback_factory(obj)
                sub = rospy.Subscriber(topic, TransformStamped, callback)
                self.subscribers.append(sub)
                rospy.loginfo(f"Subscribed to {topic}")
            except Exception as e:
                rospy.logerr(f"Failed to subscribe to {topic}: {str(e)}")
        self.is_collecting = True

    def stop(self):
        for sub in self.subscribers:
            sub.unregister()
        self.subscribers.clear()
        for obj, fh in self.file_handles.items():
            try:
                fh.close()
                rospy.loginfo(f"Closed log file for {obj}")
            except IOError as e:
                rospy.logerr(f"Error closing file for {obj}: {str(e)}")
        self.file_handles.clear()
        self.is_collecting = False

def signal_handler(sig, frame):
    print("\nShutting down gracefully...")
    logger.stop()
    rospy.signal_shutdown('User interruption')
    sys.exit(0)

def udp_listener(logger):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 10000))
    rospy.loginfo("UDP listener started on port 10000")
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode().strip()
            rospy.loginfo(f"Received UDP message: {message} from {addr}")

            if message.startswith("Start Collection:"):
                parts = message.split(':')
                if len(parts) < 2:
                    rospy.logerr("Invalid Start Collection message")
                    continue
                obj_str = parts[1].strip()
                obj_list = [obj.strip().replace("'", "") for obj in obj_str.strip("'[]").split(',')]
                logger.object_names = obj_list
                if logger.is_collecting:
                    logger.stop()
                logger.start()
                rospy.loginfo(f"Started collecting data for objects: {obj_list}")

            elif message == "End Collection":
                if logger.is_collecting:
                    logger.stop()
                    rospy.loginfo("Stopped collection and saved CSV files")
                else:
                    rospy.logwarn("No active collection to stop")
        except Exception as e:
            rospy.logerr(f"Error in UDP listener: {str(e)}")

if __name__ == '__main__':
    rospy.init_node('multi_trajectory_logger', anonymous=True)  # 

    logger = MultiTrajectoryLogger(object_names=[], output_dir='./vicon_trajectory_logs')
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    udp_thread = threading.Thread(target=udp_listener, args=(logger,))
    udp_thread.daemon = True
    udp_thread.start()
    
    rospy.spin()