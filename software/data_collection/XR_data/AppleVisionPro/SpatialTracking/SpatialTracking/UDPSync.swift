import Foundation
import Network
import Combine

class UDPSync: ObservableObject {
    static let shared = UDPSync()
    private var sendConnection: NWConnection?
    private var receiveListener: NWListener?
    private let queue = DispatchQueue(label: "UDP.Queue")
    
    @Published var timestampOffset: Double = 0
    @Published var timestampOffsetComputed = false
    var differencesList = [Double]()
    var firstTimestampReceived = false
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        startUDP()
    }
    
    private func startUDP() {
        let localIP = getLocalIPAddress()
        startReceiving()
        startContinuousIPSend(ip: localIP)
    }
    
    private func getLocalIPAddress() -> String {
        var address = "127.0.0.1"
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0 else { return address }
        
        while let ifa = ifaddr {
            if ifa.pointee.ifa_addr.pointee.sa_family == AF_INET {
                let name = String(cString: ifa.pointee.ifa_name)
                if name.hasPrefix("en") {
                    var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                    getnameinfo(ifa.pointee.ifa_addr, socklen_t(ifa.pointee.ifa_addr.pointee.sa_len),
                                &hostname, socklen_t(hostname.count),
                                nil, socklen_t(0), NI_NUMERICHOST)
                    address = String(cString: hostname)
                }
            }
            ifaddr = ifa.pointee.ifa_next
        }
        freeifaddrs(ifaddr)
        return address
    }
    
    private func startContinuousIPSend(ip: String) {
        DispatchQueue.global().async { [weak self] in
            while self?.firstTimestampReceived == false {
                self?.sendIPAddress(ip: ip)
                Thread.sleep(forTimeInterval: 1)
            }
        }
    }
    
    private func sendIPAddress(ip: String) {
        let message = "AppleVisionPro:\(ip)"
        let endpoint = NWEndpoint.hostPort(
            host: .init(SharedVariables.shared.serverIP),
            port: .init(integerLiteral: SharedVariables.shared.serverPort)
        )
        
        let connection = NWConnection(to: endpoint, using: .udp)
        connection.start(queue: queue)
        
        connection.send(content: message.data(using: .ascii), completion: .contentProcessed { error in
            if let error = error {
                print("Send error: \(error)")
            }
            connection.cancel()
        })
    }
    
    private func startReceiving() {
        do {
            let parameters = NWParameters.udp
            parameters.allowLocalEndpointReuse = true
            
            receiveListener = try NWListener(
                using: parameters,
                on: NWEndpoint.Port(integerLiteral: SharedVariables.shared.receivePort)
            )
            
            receiveListener?.stateUpdateHandler = { [weak self] state in
                switch state {
                case .ready:
                    print("UDP listener ready on port \(SharedVariables.shared.receivePort)")
                case .failed(let error):
                    print("Listener failed: \(error)")
                    self?.receiveListener?.cancel()
                case .cancelled:
                    print("Listener cancelled")
                default:
                    break
                }
            }
            
            receiveListener?.newConnectionHandler = { [weak self] newConnection in
                newConnection.start(queue: self?.queue ?? .main)
                self?.receive(on: newConnection)
            }
            
            receiveListener?.start(queue: queue)
        } catch {
            print("Failed to create UDP listener: \(error)")
        }
    }
    
    private func receive(on connection: NWConnection) {
        connection.receiveMessage { [weak self] data, _, _, error in
            guard let self = self else { return }
            
            if let error = error {
                print("Receive error: \(error)")
                return
            }
            
            guard let data = data else {
                print("Received empty data")
                return
            }
            
            if data.count == MemoryLayout<Double>.size {
                self.handleTimestamp(data)
            } else if let message = String(data: data, encoding: .ascii) {
                self.handleTextMessage(message)
            }
            
            // Continue listening
            self.receive(on: connection)
        }
    }
    
    private func handleTimestamp(_ data: Data) {
        if !firstTimestampReceived {
            firstTimestampReceived = true
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy_MM_dd_HH_mm"
            SharedVariables.shared.uploadFileName = "AppleVisionPro_\(formatter.string(from: Date())).csv"
        }
        
        let serverTimestamp = data.withUnsafeBytes { $0.load(as: Double.self) }
        let localTimestamp = Date().timeIntervalSince1970
        let difference = serverTimestamp - localTimestamp
        
        DispatchQueue.main.async {
            self.differencesList.append(difference)
        }
    }
    
    private func handleTextMessage(_ message: String) {
        switch message {
        case "Stop Sync":
            print("Received stop sync message")
            computeAverageOffset()
        case "Stop Collection":
            print("Received stop collection message")
            SharedVariables.shared.quitApp = true
        default:
            print("Received unknown message: \(message)")
        }
    }
    
    private func computeAverageOffset() {
        DispatchQueue.main.async {
            guard !self.differencesList.isEmpty else {
                print("No timestamps received for offset calculation")
                return
            }
            // Use the last half of the differences list to computer the average offset
            let halfIndex = self.differencesList.count / 2
            self.differencesList = Array(self.differencesList.suffix(from: halfIndex))
            self.timestampOffset = self.differencesList.reduce(0, +) / Double(self.differencesList.count)
            self.timestampOffsetComputed = true
            print("Computed average offset: \(self.timestampOffset)s")
        }
    }
    
    deinit {
        receiveListener?.cancel()
        sendConnection?.cancel()
        print("UDPSync cleaned up")
    }
}
