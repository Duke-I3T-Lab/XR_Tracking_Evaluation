//
//  AppModel.swift
//  SpatialTracking
//
//  Created by I3T Duke on 3/15/25.
//

import SwiftUI

/// Maintains app-wide state
@MainActor
@Observable
class AppModel {
    let immersiveSpaceID = "ImmersiveSpace"
    enum ImmersiveSpaceState {
        case closed
        case inTransition
        case open
    }
    var immersiveSpaceState = ImmersiveSpaceState.closed
    
    // !!!!!!!!!!!!!!!!!!!!!!!!
    // Set it to open to ensure the immersive space is open when the app starts.
    // So that the device anchor is created and the device is tracked.
    // See https://developer.apple.com/forums/thread/761167
}
