using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.InputSystem;

public class HeadTracking : MonoBehaviour
{
    private InputAction headPositionAction;
    private InputAction headRotationAction;

    private string csvFilePath;
    private StreamWriter writer;
    private bool bufferWritten = false;
    private bool isSaving = false;

    // Thread-safe collections
    private ConcurrentQueue<string> dataQueue = new ConcurrentQueue<string>();
    private ConcurrentQueue<(double, string)> bufferedQueue = new ConcurrentQueue<(double, string)>();

    // Batch processing parameters
    private const int WRITE_BATCH_SIZE = 50;
    private const int WRITE_INTERVAL_MS = 100;


    private bool uploadTriggered = false;
    private WebClient client;


    async void Start()
    {
        InitializeInputActions();
        InitializeCSVFile();
        await StartFileWriter();
    }

    void InitializeInputActions()
    {
        headPositionAction = new InputAction(binding: "<OpenXRHmd>/devicePosition");
        headRotationAction = new InputAction(binding: "<OpenXRHmd>/deviceRotation");
        headPositionAction.Enable();
        headRotationAction.Enable();
    }

    void InitializeCSVFile()
    {
        csvFilePath = Path.Combine(Application.persistentDataPath, "HeadTrackingData.csv");
        writer = new StreamWriter(csvFilePath);
        writer.WriteLine("timestamp,pos_x,pos_y,pos_z,qua_1,qua_2,qua_3,qua_4");
    }

    async Task StartFileWriter()
    {
        isSaving = true;
        while (isSaving)
        {
            await WriteBatchToFile();
            await Task.Delay(WRITE_INTERVAL_MS);
        }
    }

    void Update()
    {
        CaptureFrameData();
        if (SharedVariables.Instance.quitApp && !uploadTriggered)
        {
            uploadTriggered = true;
            PrepareForUpload();
        }
    }

    async void PrepareForUpload()
    {
        // Stop data collection and writing
        isSaving = false;

        if (bufferedQueue.Count > 0)
        {
            ProcessBufferedData();
        }
        Debug.Log("BetaTest: Final data write...");

        // Wait for final write operation to complete
        await WriteBatchToFile();

        Debug.Log("BetaTest: Closing Writer...");

        // Close the writer
        writer?.Close();
        writer?.Dispose();

        Debug.Log("BetaTest: Starting upload...");

        // Start upload
        UploadFileFTP();
    }

    private async void UploadFileFTP()
    {
        Debug.Log("BetaTest: Uploading file to FTP server...");
        try
        {

            client = new WebClient();
            client.Credentials = new NetworkCredential(SharedVariables.Instance.ftpUsername, SharedVariables.Instance.ftpPassword);

            string ftpString = $"ftp://{SharedVariables.Instance.serverIP}:{SharedVariables.Instance.ftpPort}/{SharedVariables.Instance.uploadFileName}";
            Debug.Log("BetaTest: FTP String: " + ftpString);
            Debug.Log("Beta Test: uploadFileName: " + SharedVariables.Instance.uploadFileName);

            // Use UploadFileTaskAsync for proper async/await
            await client.UploadFileTaskAsync(
                new Uri($"ftp://{SharedVariables.Instance.serverIP}:{SharedVariables.Instance.ftpPort}/{SharedVariables.Instance.uploadFileName}"),
                "STOR",
                csvFilePath
            );

            Debug.Log("BetaTest: File uploaded successfully");
        }
        catch (Exception e)
        {
            Debug.LogError($"Upload failed: {e.Message}");
        }
        finally
        {
            client?.Dispose();

            // Fully quit the application after upload
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }
    }

    void CaptureFrameData()
    {
        // Debug.Log("BetaTest: Capturing frame data...");
        var headPosition = headPositionAction.ReadValue<Vector3>();
        var headRotation = headRotationAction.ReadValue<Quaternion>();
        var currentTime = Time.timeAsDouble;

        if (!SharedVariables.Instance.timestampOffsetComputed)
        {
            BufferData(currentTime, headPosition, headRotation);
        }
        else
        {
            ProcessCurrentData(currentTime, headPosition, headRotation);
        }
    }

    void BufferData(double currentTime, Vector3 position, Quaternion rotation)
    {
        var data = $"{position.x},{position.y},{position.z}," +
                   $"{rotation.x},{rotation.y},{rotation.z},{rotation.w}";
        bufferedQueue.Enqueue((currentTime, data));
    }

    void ProcessCurrentData(double currentTime, Vector3 position, Quaternion rotation)
    {
        if (!bufferWritten)
        {
            ProcessBufferedData();
            bufferWritten = true;
        }

        var adjustedTime = currentTime + SharedVariables.Instance.timestampOffset;
        var data = $"{adjustedTime},{position.x},{position.y},{position.z}," +
                   $"{rotation.x},{rotation.y},{rotation.z},{rotation.w}";
        dataQueue.Enqueue(data);
    }

    void ProcessBufferedData()
    {
        while (bufferedQueue.TryDequeue(out var item))
        {
            var adjustedTime = item.Item1 + SharedVariables.Instance.timestampOffset;
            dataQueue.Enqueue($"{adjustedTime},{item.Item2}");
        }
    }

    async Task WriteBatchToFile()
    {
        var batch = new List<string>();
        while (batch.Count < WRITE_BATCH_SIZE && dataQueue.TryDequeue(out var data))
        {
            batch.Add(data);
        }


        if (batch.Count > 0)
        {
            Debug.Log("BetaTest: Writing batch to file...");
            await writer.WriteLineAsync(string.Join(Environment.NewLine, batch));
            await writer.FlushAsync();
        }
    }

    void OnDestroy()
    {
        // Prevent duplicate cleanup
        if (uploadTriggered) return;

        isSaving = false;
        headPositionAction.Disable();
        headRotationAction.Disable();

        // Final data write if somehow missed
        WriteBatchToFile().Wait();
        writer?.Close();
        writer?.Dispose();
    }
}