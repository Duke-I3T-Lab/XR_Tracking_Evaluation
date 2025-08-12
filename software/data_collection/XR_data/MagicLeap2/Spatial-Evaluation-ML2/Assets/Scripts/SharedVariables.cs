using UnityEngine;
using System;
using System.Threading.Tasks;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine.InputSystem;
using UnityEngine.Events;

public class SharedVariables : MonoBehaviour
{
    public static SharedVariables Instance;
    // public long receivedTimestamp = 0;

    // private bool isRunning = true;

    public bool quitApp = false;

    public string serverIP = "192.168.1.1";
    public int serverPort = 12345;
    public int receivePort = 54321;

    public string ftpUsername = "";
    public string ftpPassword = "";
    public int ftpPort = 21;


    // private UdpClient udpClient;
    // private Thread udpThread;

    private InputAction triggerAction;

    // public UnityEvent<bool> SavePointCloudDataEvent;

    public double timestampOffset = 0;

    public bool timestampOffsetComputed = false;

    public bool stopCapture = false;

    public string uploadFileName = "test_file.csv";


    public void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else if (Instance != this)
        {
            Destroy(gameObject);
        }
    }
    void Start()
    {
        // Initialize UDP receiver
        /*
        udpClient = new UdpClient(5555); // Use port 5555 for receiving timestamps
        udpThread = new Thread(new ThreadStart(ReceiveTimestamps));
        udpThread.IsBackground = true;
        udpThread.Start();
        */

        // Initialize input actions for trigger button
        triggerAction = new InputAction(binding: "<MagicLeapController>/trigger");
        triggerAction.Enable();

    }
    /*
    private void ReceiveTimestamps()
    {
        try
        {
            IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);

            while (isRunning)
            {
                byte[] receivedBytes = udpClient.Receive(ref remoteEndPoint);
                string timestampString = Encoding.UTF8.GetString(receivedBytes);
                long.TryParse(timestampString, out receivedTimestamp);
                if (receivedTimestamp == -1) quitApp = true;

            }
        }
        catch (Exception e)
        {
            Debug.LogError($"UDP Receiver Error: {e.Message}");
        }
    }

    */

    // Update is called once per frame
    void Update()
    {
        if (triggerAction.ReadValue<float>() > 0.5f)
        {
            Debug.Log("BetaTest: Trigger pressed");
            quitApp = true;
        }

        // if (quitApp)
        // {
        //     SavePointCloudDataEvent.Invoke(true);
        // }
        // quitApp = false;


    }

    void OnDestroy()
    {
        // Clean up resources on destroy
        // udpThread?.Abort();
        // udpClient?.Close();

        // isRunning = false;
        triggerAction.Disable();
    }
}
