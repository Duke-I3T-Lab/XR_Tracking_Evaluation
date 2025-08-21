#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import TransformStamped
import os
import socket
from datetime import datetime
import time

def callback(data):
    # Combine secs and nsecs into a millisecond-level timestamp
    timestamp = data.header.stamp.secs + data.header.stamp.nsecs / 1000000000
    print(timestamp)

def listener():
    rospy.init_node('listener', anonymous=True)
    rospy.Subscriber("/vicon/wand/wand", TransformStamped, callback)
    rospy.spin()

if __name__ == '__main__':
    listener()