using System.Collections;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using MagicLeap.Android;
using MagicLeap.OpenXR.Features.Meshing;

public class PointCloudCapture : MonoBehaviour
{
    [SerializeField] private ARPointCloudManager pointCloudManager;
    private MagicLeapMeshingFeature meshingFeature;

    // Search for the Mesh Manager and assign it automatically if it was not set in the inspector
    private void OnValidate()
    {
        if (pointCloudManager == null)
        {
            pointCloudManager = FindObjectOfType<ARPointCloudManager>();
        }
    }

    IEnumerator Start()
    {
        // Check if the ARPointCloudManager component is assigned, if not, try to find one in the scene
        if (pointCloudManager == null)
        {
            Debug.LogError("No ARMeshManager component found. Disabling script.");
            enabled = false;
            yield break;
        }

        pointCloudManager.enabled = false;
        yield return new WaitUntil(() => IsMeshingSubsystemLoaded());

        meshingFeature = OpenXRSettings.Instance.GetFeature<MagicLeapMeshingFeature>();
        if (!meshingFeature.enabled)
        {
            Debug.LogError($"{nameof(MagicLeapMeshingFeature)} was not enabled. Disabling script");
            enabled = false;
        }

        Permissions.RequestPermission(Permissions.SpatialMapping, OnPermissionGranted, OnPermissionDenied, OnPermissionDenied);
    }

    private void OnPermissionGranted(string permission)
    {
        pointCloudManager.enabled = true;
    }

    private void OnPermissionDenied(string permission)
    {
        Debug.LogError($"Failed to create Planes Subsystem due to missing or denied {Permissions.SpatialMapping} permission. Please add to manifest. Disabling script.");
        enabled = false;
    }

    private bool IsMeshingSubsystemLoaded()
    {
        if (XRGeneralSettings.Instance == null || XRGeneralSettings.Instance.Manager == null) return false;
        var activeLoader = XRGeneralSettings.Instance.Manager.activeLoader;
        Debug.Log($"Meshing Subsystem Active loader: {activeLoader}");
        return activeLoader != null && activeLoader.GetLoadedSubsystem<XRMeshSubsystem>() != null;
    }
}