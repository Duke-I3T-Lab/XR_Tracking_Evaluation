//
//  SharedVariables.swift
//  SpatialTracking
//
//  Created by I3T Duke on 3/18/25.
//

// File: SharedVariables.swift
import Foundation
import Combine

class SharedVariables: ObservableObject {
    static let shared = SharedVariables()
    
    @Published var serverIP = "192.168.0.108" //"192.168.0.108"
    @Published var serverPort: UInt16 = 6666
    @Published var receivePort: UInt16 = 8888
    @Published var ftpUsername = ""
    @Published var ftpPassword = ""
    @Published var ftpPort: UInt16 = 21
    @Published var quitApp = false
    @Published var uploadFileName = "test_file.csv"
    @Published var webSocketport: UInt16 = 8765
}
