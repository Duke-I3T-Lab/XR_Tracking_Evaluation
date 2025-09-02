// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2017 Intel Corporation. All Rights Reserved.

#include <librealsense2/rs.hpp>
#include <opencv2/opencv.hpp>
#include <iostream>
#include <fstream>
#include <sstream>
#include <map>
#include <chrono>
#include <mutex>
#include <thread>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <filesystem>
#include <ifaddrs.h>
#include <iomanip>
#include <cstring>

// Replace the filesystem namespace alias at the top
#if __has_include(<filesystem>)
#include <filesystem>
namespace fs = std::filesystem;
#elif __has_include(<experimental/filesystem>)
#include <experimental/filesystem>
namespace fs = std::experimental::filesystem;
#else
#error "No filesystem support"
#endif

// Global parameters
std::mutex mutex;
bool collecting = false;
double imu_timestamp = 0;
rs2_vector accel_data = {};
rs2_vector gyro_data = {};
bool accel_updated = false;
bool gyro_updated = false;

std::string get_local_ip() {
    struct ifaddrs *ifaddr, *ifa;
    std::string ip = "127.0.0.1";
    if (getifaddrs(&ifaddr) == -1) return ip;

    for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
        if (!ifa->ifa_addr) continue;
        if (ifa->ifa_addr->sa_family == AF_INET) {
            std::string interface_name = ifa->ifa_name;
            std::string current_ip = inet_ntoa(((struct sockaddr_in*)ifa->ifa_addr)->sin_addr);
            if (current_ip != "127.0.0.1" && interface_name != "lo") {
                ip = current_ip;
                break;
            }
        }
    }
    freeifaddrs(ifaddr);
    return ip;
}

void send_udp_message(const std::string& message) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) return;

    struct sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(6666);
    inet_pton(AF_INET, "192.168.0.108", &server_addr.sin_addr);

    sendto(sock, message.c_str(), message.size(), 0, 
          (struct sockaddr*)&server_addr, sizeof(server_addr));
    close(sock);
}

void rename_data_folder() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    std::tm tm_buf{};
    localtime_r(&in_time_t, &tm_buf);
    
    std::stringstream ss;
    ss << std::put_time(&tm_buf, "%Y%m%d_%H%M%S");
    std::string new_name = "data_" + ss.str();

    // Check and handle folder rename
    int rename_status = system(("mv data " + new_name).c_str());
    if (rename_status != 0) {
        std::cerr << "Failed to rename data folder: " << rename_status << std::endl;
    }

    // Create new directories with error checking
    auto create_dir = [](const char* path) {
        int status = system((std::string("mkdir -p ") + path).c_str());
        if (status != 0) {
            std::cerr << "Failed to create directory " << path 
                     << ": error " << status << std::endl;
        }
    };

    create_dir("data/cam0");
    create_dir("data/cam1");
    create_dir("data/imu");
}

void handle_imu(const rs2::frame &f, std::ofstream &imu_file) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!collecting) return;

    if (f.get_profile().unique_id() == 7) {
        imu_timestamp = f.get_timestamp() / 1000;
        accel_data = f.as<rs2::motion_frame>().get_motion_data();
        accel_updated = true;
    } else if (f.get_profile().unique_id() == 8) {
        gyro_data = f.as<rs2::motion_frame>().get_motion_data();
        gyro_updated = true;
    }

    if (accel_updated && gyro_updated) {
        imu_file << std::fixed << std::setprecision(6) << imu_timestamp << ","
                << gyro_data.x << "," << gyro_data.y << "," << gyro_data.z << ","
                << accel_data.x << "," << accel_data.y << "," << accel_data.z << std::endl;
        accel_updated = false;
        gyro_updated = false;
    }
}

void check_frame(const rs2::frame &f, std::ofstream &cam1_file, std::ofstream &cam2_file, std::ofstream &imu_file) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!collecting) return;

    int id = f.get_profile().unique_id();
    double timestamp = f.get_timestamp() / 1000;

    if (id == 1) {
        rs2::video_frame infrared_frame = f.as<rs2::video_frame>();
        std::stringstream filename;
        filename << "./data/cam0/" << std::fixed << std::setprecision(6) << timestamp << ".png";
        
        cv::Mat infrared_mat(cv::Size(640, 480), CV_8U, (void*)infrared_frame.get_data(), cv::Mat::AUTO_STEP);
        cv::imwrite(filename.str(), infrared_mat);
        cam1_file << std::fixed << std::setprecision(6) << timestamp << " " << filename.str() << std::endl;
    } else if (id == 2) {
        rs2::video_frame infrared_frame = f.as<rs2::video_frame>();
        std::stringstream filename;
        filename << "./data/cam1/" << std::fixed << std::setprecision(6) << timestamp << ".png";
        
        cv::Mat infrared_mat(cv::Size(640, 480), CV_8U, (void*)infrared_frame.get_data(), cv::Mat::AUTO_STEP);
        cv::imwrite(filename.str(), infrared_mat);
        cam2_file << std::fixed << std::setprecision(6) << timestamp << " " << filename.str() << std::endl;
    } else {
        handle_imu(f, imu_file);
    }
}

int main() try {
    // Create initial data directories
    auto create_dir = [](const char* path) {
        int status = system((std::string("mkdir -p ") + path).c_str());
        if (status != 0) {
            std::cerr << "Initial directory creation failed for " << path 
                     << ": error " << status << std::endl;
            exit(EXIT_FAILURE);
        }
    };
    
    create_dir("data/cam0");
    create_dir("data/cam1");
    create_dir("data/imu");

    // Setup UDP socket
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        std::cerr << "Failed to create socket: " << strerror(errno) << std::endl;
        return EXIT_FAILURE;
    }

    int reuse = 1;
    if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse)) < 0) {
        std::cerr << "Failed to set SO_REUSEADDR: " << strerror(errno) << std::endl;
        close(sock);
        return EXIT_FAILURE;
    }

    struct sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    server_addr.sin_port = htons(11111);

    if (bind(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "Bind failed: " << strerror(errno) << std::endl;
        close(sock);
        return EXIT_FAILURE;
    }

    fcntl(sock, F_SETFL, O_NONBLOCK);

    // Initialize RealSense pipeline
    rs2::pipeline pipe;
    rs2::pipeline_profile profiles;
    rs2::config cfg;

    cfg.disable_all_streams();
    cfg.enable_stream(RS2_STREAM_GYRO, RS2_FORMAT_MOTION_XYZ32F, 200);
    cfg.enable_stream(RS2_STREAM_ACCEL, RS2_FORMAT_MOTION_XYZ32F, 200);
    cfg.enable_stream(RS2_STREAM_INFRARED, 1, 640, 480, RS2_FORMAT_Y8, 30);
    cfg.enable_stream(RS2_STREAM_INFRARED, 2, 640, 480, RS2_FORMAT_Y8, 30);

    std::ofstream cam1_file("./data/cam0.csv");
    std::ofstream cam2_file("./data/cam1.csv");
    std::ofstream imu_file("./data/imu/data.csv");

    auto callback = [&](const rs2::frame &frame) {
        if (rs2::frameset fs = frame.as<rs2::frameset>()) {
            for (const rs2::frame &f : fs) {
                check_frame(f, cam1_file, cam2_file, imu_file);
            }
        } else {
            handle_imu(frame, imu_file);
        }
    };

    profiles =  pipe.start(cfg, callback);

    std::map<int, std::string> stream_names;  // Map to store stream names by unique_id

    // Collect the enabled stream names
    for (auto p : profiles.get_streams())
    {
        stream_names[p.unique_id()] = p.stream_name();  // Store stream name by unique_id
        std::cout << "Stream Profile " << p.stream_type() << "[" << p.unique_id() << "], format " << p.format() << " at " << p.fps() << " fps" << std::endl;
    }

    // Configure sensors
    std::vector<rs2::sensor> sensors = profiles.get_device().query_sensors();
    int index = 0;
    for (rs2::sensor sensor : sensors)
    {
        if (sensor.supports(RS2_CAMERA_INFO_NAME))
        {
            ++index;
            if (index == 1)
            {
                // Configure the first sensor (e.g., Infrared)
                std::cout << sensor.get_info(RS2_CAMERA_INFO_NAME) << std::endl;
                sensor.set_option(RS2_OPTION_ENABLE_AUTO_EXPOSURE, 1);  // Enable auto-exposure
                sensor.set_option(RS2_OPTION_AUTO_EXPOSURE_LIMIT,5000);
                sensor.set_option(RS2_OPTION_EMITTER_ENABLED, 0);  // Disable emitter
            }
            if (index == 2)
            {
                // Configure the second sensor (e.g., RGB camera)
                std::cout << sensor.get_info(RS2_CAMERA_INFO_NAME) << std::endl;
                // RGB camera (not used here...)
                sensor.set_option(RS2_OPTION_EXPOSURE, 100.f);  // Set exposure to 100 ms
            }
            if (index == 3)
            {
                // Configure the third sensor (e.g., IMU)
                std::cout << sensor.get_info(RS2_CAMERA_INFO_NAME) << std::endl;
                sensor.set_option(RS2_OPTION_ENABLE_MOTION_CORRECTION, 0);  // Disable motion correction
            }
        }
    }

    // Initialization period
    std::cout << "Initializing sensor for 3 seconds..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(3));
    send_udp_message("SensorCollector:" + get_local_ip());
    std::cout << "Initialization complete. Waiting for commands." << std::endl;

    // Main loop
    bool running = true;
    while (running) {
        char buffer[1024];
        struct sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        
        ssize_t n = recvfrom(sock, buffer, sizeof(buffer)-1, 0,
                            (struct sockaddr *)&client_addr, &client_len);
        if (n > 0) {
            std::string message(buffer, n);
            std::lock_guard<std::mutex> lock(mutex);
            
            if (message == "Start Collection") {
                collecting = true;
                std::cout << "Data collection started." << std::endl;
            } else if (message == "End Collection") {
                collecting = false;
                running = false;
                std::cout << "Data collection stopped." << std::endl;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Cleanup
    pipe.stop();
    close(sock);
    cam1_file.close();
    cam2_file.close();
    imu_file.close();
    rename_data_folder();

    return EXIT_SUCCESS;
}
catch (const rs2::error &e) {
    std::cerr << "RealSense error: " << e.what() << std::endl;
    return EXIT_FAILURE;
}
catch (const std::exception &e) {
    std::cerr << "Error: " << e.what() << std::endl;
    return EXIT_FAILURE;
}