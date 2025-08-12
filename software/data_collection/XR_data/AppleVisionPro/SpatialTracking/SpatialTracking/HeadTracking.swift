//
//  HeadTracking.swift
//  SpatialTracking
//
//  Created by I3T Duke on 3/18/25.
//


import Foundation
import Vision
import os.log
import QuartzCore
import ARKit
import Combine
import Network

class HeadTracking: ObservableObject {
    static let shared = HeadTracking()
    private let arkitSession = ARKitSession()
    private let worldTracking = WorldTrackingProvider()
    private var fileQueue = DispatchQueue(label: "FileQueue")
    private var csvFile: FileHandle?
    private var fileURL: URL?
    private var isSaving = false
    private var buffer = [(Double, String)]()
    private var isTracking = false // Step 1: Track session state
    
    private var cancellables = Set<AnyCancellable>()
    private var uploadTriggered = false
    
    private var uploadStatus: String = ""
    private var isUploading: Bool = false
    
    init() {
        // Set up quitApp observer
        SharedVariables.shared.$quitApp
            .receive(on: DispatchQueue.main)
            .sink { [weak self] shouldQuit in
                guard let self = self, shouldQuit, !self.uploadTriggered else { return }
                self.prepareForUpload()
                self.uploadTriggered = true
                // Quit the app after a successful upload after 3 second
//                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
//                    exit(0)
//                }
            }
            .store(in: &cancellables)
    }
    
    func startTracking() async {
        do {
            try await arkitSession.run([worldTracking])
            isTracking = true // Step 2: Set tracking state
            var fileName = SharedVariables.shared.uploadFileName
            while fileName == "test_file.csv" {
                fileName = SharedVariables.shared.uploadFileName
                try await Task.sleep(nanoseconds: 1_000_000_000)
            }
            try await Task.sleep(nanoseconds: 1_000_000_000)
            setupCSVFile()
            isSaving = true
            startBatchProcessing()
        } catch {
            os_log("Failed to start AR session: %@", error.localizedDescription)
        }
    }
    
    private func setupCSVFile() {
        print("Setting up CSV file")
        let fileName = SharedVariables.shared.uploadFileName
        fileURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(fileName)
        
        // Ensure the directory structure exists
        let directoryURL = fileURL!.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(
                at: directoryURL,
                withIntermediateDirectories: true,
                attributes: nil
            )
        } catch {
            print("Failed to create directory: \(error)")
            return
        }
        
        print("File URL: \(fileURL!.path)")
        
        // Explicitly check if file creation succeeds
        guard FileManager.default.createFile(atPath: fileURL!.path, contents: nil) else {
            print("Failed to create file at \(fileURL!.path)")
            return
        }
        
        csvFile = try? FileHandle(forWritingTo: fileURL!)
        writeHeader()
    }
    private func writeHeader() {
        print("Writing header to CSV file at \(fileURL?.path ?? "unknown path")")
        let header = "timestamp pos_x pos_y pos_z qua_1 qua_2 qua_3 qua_4\n"
        csvFile?.write(header.data(using: .utf8)!)
    }
    
    func captureFrame() {
        guard isTracking else { return }
        do {
            //let timestamp = CACurrentMediaTime()//Date().timeIntervalSince1970
            let timestamp = Date().timeIntervalSince1970
            
            // Query device anchor and safely unwrap the optional
            //guard let deviceAnchor = try worldTracking.queryDeviceAnchor(atTimestamp: timestamp) else {
            guard let deviceAnchor = try worldTracking.queryDeviceAnchor(atTimestamp: CACurrentMediaTime()) else {
                os_log("Device anchor unavailable at timestamp \(timestamp)")
                return
            }
            
            // Now `deviceAnchor` is non-optional
            let originFromAnchorTransform = deviceAnchor.originFromAnchorTransform
            
            let position = SIMD3<Float>(
                originFromAnchorTransform.columns.3.x,
                originFromAnchorTransform.columns.3.y,
                originFromAnchorTransform.columns.3.z
            )
            
            let rotation = simd_quatf(originFromAnchorTransform)
            
            if !UDPSync.shared.timestampOffsetComputed {
                bufferData(timestamp: timestamp, position: position, rotation: rotation)
            } else {
                processData(timestamp: timestamp, position: position, rotation: rotation)
            }
        } catch {
            os_log("Failed to query device anchor: %@", error.localizedDescription)
        }
    }
    
    private func bufferData(timestamp: Double, position: SIMD3<Float>, rotation: simd_quatf) {
        let data = "\(position.x) \(position.y) \(position.z) \(rotation.vector.x) \(rotation.vector.y) \(rotation.vector.z) \(rotation.vector.w)"
        buffer.append((timestamp, data))
        
    }
    
    private func processData(timestamp: Double, position: SIMD3<Float>, rotation: simd_quatf) {
        if !buffer.isEmpty {
            processBuffer()
        }
        
        let adjustedTime = timestamp + UDPSync.shared.timestampOffset
        let data = "\(adjustedTime) \(position.x) \(position.y) \(position.z) \(rotation.vector.x) \(rotation.vector.y) \(rotation.vector.z) \(rotation.vector.w)\n"
        if isSaving {
            writeToFile(data: data)
        }
    }
    
    private func processBuffer() {
        for (timestamp, data) in buffer {
            let adjustedTime = timestamp + UDPSync.shared.timestampOffset
            writeToFile(data: "\(adjustedTime) \(data)\n")
        }
        buffer.removeAll()
    }
    
    private func startBatchProcessing() {
        fileQueue.async { [weak self] in
            while self?.isSaving == true {
                Thread.sleep(forTimeInterval: 0.1)
                self?.csvFile?.synchronizeFile()
            }
        }
    }
    
    private func writeToFile(data: String) {
        //print("Writing data: \(data)")
        fileQueue.async {
            self.csvFile?.write(data.data(using: .utf8)!)
        }
    }

    func sendCSVFile(serverURL: String, fileURL: URL) async throws {
        let session = URLSession(configuration: .default)
        let webSocketTask = session.webSocketTask(with: URL(string: serverURL)!)
        webSocketTask.resume()
        
        // Read file data
        let data = try Data(contentsOf: fileURL)
        
        // Use smaller chunks (e.g., 64KB)
        let chunkSize = 65_536 // 64KB
        var offset = 0
        
        while offset < data.count {
            let end = min(offset + chunkSize, data.count)
            let chunk = data.subdata(in: offset..<end)
            let message = URLSessionWebSocketTask.Message.data(chunk)
            
            // Send chunk
            try await webSocketTask.send(message)
            print("Sent chunk: \(offset)-\(end)")
            offset = end
        }
        
        print("All chunks sent successfully")
        
        // Explicitly send close frame to initiate handshake
        try await webSocketTask.send(.string("EOF")) // Optional: Signal end of file
        webSocketTask.cancel(with: .normalClosure, reason: nil)
        
        // Wait for server's close acknowledgment
        do {
            _ = try await webSocketTask.receive()
            print("Server acknowledged closure")
        } catch {
            print("Connection closed: \(error)")
        }
    }
    
//    func sendCSVFile(serverURL: String, fileURL: URL) async throws {
//        let session = URLSession(configuration: .default)
//        let webSocketTask = session.webSocketTask(with: URL(string: serverURL)!)
//        webSocketTask.resume()
//        
//        defer {
//            webSocketTask.cancel(with: .normalClosure, reason: nil)
//        }
//        
//        // Read file data
//        let data = try Data(contentsOf: fileURL)
//        
//        // Create binary message
//        let message = URLSessionWebSocketTask.Message.data(data)
//        
//        // Send data
//        try await webSocketTask.send(message)
//        print("File sent successfully")
//        
//        
//        DispatchQueue.main.asyncAfter(deadline: .now() + 10) {
//            // Allow some time for the server to process the file
//            // After this delay, you can handle any cleanup or further actions
//            print("Finished sending CSV file to server. You can now proceed with any further actions.")
//            // You can also set a flag here to indicate that the upload is complete
//            exit(0) // Exit the app after sending the file, if needed
//        }
//    }
    
    
    func prepareForUpload() {
        isSaving = false
        isTracking = false // Step 2: Stop tracking
        arkitSession.stop() // Step 2: Stop AR session
        fileQueue.sync {
            csvFile?.synchronizeFile()
            csvFile?.closeFile()
        }
        let serverURL = "ws://\(SharedVariables.shared.serverIP):\(SharedVariables.shared.webSocketport)"
        Task {
            do {
                try await sendCSVFile(serverURL: serverURL, fileURL: fileURL!)
            } catch {
                print("Failed to send file: \(error)")
            }
        }
        
    }
    
}



