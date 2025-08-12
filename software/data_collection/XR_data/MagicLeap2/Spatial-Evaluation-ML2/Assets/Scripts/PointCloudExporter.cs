using UnityEngine;
using UnityEngine.XR.ARFoundation;
using System.Collections.Generic;
using System.IO;

public class PointCloudExporter : MonoBehaviour
{
    [SerializeField] private ARPointCloudManager pointCloudManager;

    public void savePointCloudData(bool quitAfterSave = true)
    {
        if (pointCloudManager == null) return;

        var points = new List<Vector3>();
        foreach (var cloud in pointCloudManager.trackables)
        {
            if (cloud.positions.HasValue)
            {
                points.AddRange(cloud.positions.Value);
            }
        }

        SaveAsPLY(points);

        if (quitAfterSave)
        {
            Application.Quit();
        }
    }

    private void SaveAsPLY(List<Vector3> points)
    {
        Debug.Log("Saving point cloud data...");
        string path = Path.Combine(Application.persistentDataPath, "final_scan.ply");
        using (StreamWriter writer = new StreamWriter(path))
        {
            writer.WriteLine("ply");
            writer.WriteLine("format ascii 1.0");
            writer.WriteLine($"element vertex {points.Count}");
            writer.WriteLine("property float x");
            writer.WriteLine("property float y");
            writer.WriteLine("property float z");
            writer.WriteLine("end_header");

            foreach (var p in points)
            {
                writer.WriteLine($"{p.x} {p.y} {p.z}");
            }
        }
        Debug.Log($"Point cloud data saved to {path}");
    }
}
