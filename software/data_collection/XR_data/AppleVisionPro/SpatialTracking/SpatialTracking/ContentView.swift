////
////  ContentView.swift
////  SpatialTracking
////
////  Created by I3T Duke on 3/15/25.
////
//
//import SwiftUI
//import RealityKit
//import RealityKitContent
//
//struct ContentView: View {
//
//    @State private var enlarge = false
//    
//    @StateObject private var udpSync = UDPSync.shared
//    @StateObject private var headTracking = HeadTracking.shared
//
//    var body: some View {
//        RealityView { content in
//            // Add the initial RealityKit content
//            if let scene = try? await Entity(named: "Scene", in: realityKitContentBundle) {
//                content.add(scene)
//            }
//        } update: { content in
//            // Update the RealityKit content when SwiftUI state changes
//            if let scene = content.entities.first {
//                let uniformScale: Float = enlarge ? 1.4 : 1.0
//                scene.transform.scale = [uniformScale, uniformScale, uniformScale]
//            }
//        }
//        .gesture(TapGesture().targetedToAnyEntity().onEnded { _ in
//            enlarge.toggle()
//        })
//        .toolbar {
//            ToolbarItemGroup(placement: .bottomOrnament) {
//                VStack (spacing: 12) {
//                    Button {
//                        enlarge.toggle()
//                    } label: {
//                        Text(enlarge ? "Reduce RealityView Content" : "Enlarge RealityView Content")
//                    }
//                    .animation(.none, value: 0)
//                    .fontWeight(.semibold)
//
//                    ToggleImmersiveSpaceButton()
//                }
//            }
//        }
//        .task {
//            await headTracking.startTracking()
//        }
//    }
//}
//
//#Preview(windowStyle: .volumetric) {
//    ContentView()
//        .environment(AppModel())
//}


import SwiftUI
import RealityKit
import RealityKitContent
import Combine

struct ContentView: View {
    @State private var enlarge = false
    @StateObject private var udpSync = UDPSync.shared
    @StateObject private var headTracking = HeadTracking.shared
    @State private var frameUpdateTask: Task<Void, Never>?
    
    var body: some View {
        RealityView { content in
//            if let scene = try? await Entity(named: "Scene", in: realityKitContentBundle) {
//                content.add(scene)
//            }
        }
//        .gesture(TapGesture().targetedToAnyEntity().onEnded { _ in
//            enlarge.toggle()
//        })
        .task {
            // Start head tracking when view appears
            await headTracking.startTracking()
            
            // Start frame capture loop
            frameUpdateTask = Task(priority: .userInitiated) {
                while !Task.isCancelled {
                    // Capture at ~90Hz (adjust interval for your needs)
                    try? await Task.sleep(nanoseconds: 11_111_111) // ~90Hz
                    headTracking.captureFrame()
                }
            }
        }
        .onDisappear {
            // Clean up when view disappears
            frameUpdateTask?.cancel()
        }
        .toolbar {
            ToolbarItemGroup(placement: .bottomOrnament) {
                VStack(spacing: 12) {
                    Button {
                        enlarge.toggle()
                    } label: {
                        Text(enlarge ? "Reduce Content" : "Enlarge Content")
                    }
                    .fontWeight(.semibold)
                    
                    ToggleImmersiveSpaceButton()
                }
            }
        }
    }
}
#Preview(windowStyle: .volumetric) {
    ContentView()
        .environment(AppModel())
}
