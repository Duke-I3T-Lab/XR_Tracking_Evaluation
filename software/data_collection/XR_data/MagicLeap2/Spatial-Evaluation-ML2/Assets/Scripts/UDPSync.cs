using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Linq;

public class UDPSync : MonoBehaviour
{


    private UdpClient sendClient;
    private UdpClient receiveClient;
    private Thread receiveThread;
    private bool isListening;
    private List<double> differencesList = new List<double>();
    private double timestampOffset;

    private bool firstTimestampReceived = false;
    private Thread sendThread;
    private bool stopSending = false;


    void Start()
    {
        string localIP = GetLocalIPAddress();
        if (string.IsNullOrEmpty(localIP))
        {
            Debug.LogError("Could not find local IPv4 address");
            return;
        }

        // Start UDP listening thread
        isListening = true;
        receiveThread = new Thread(new ThreadStart(ReceiveData));
        receiveThread.IsBackground = true;
        receiveThread.Start();


        // Start continuous IP sending thread
        sendThread = new Thread(() => ContinuousIPSend(localIP));
        sendThread.IsBackground = true;
        sendThread.Start();


    }

    private void ContinuousIPSend(string localIP)
    {
        try
        {
            while (!stopSending && !firstTimestampReceived)
            {
                SendIPAddress(localIP, "MagicLeap2");
                Thread.Sleep(1000); // Wait 1 second between sends
            }
        }
        catch (ThreadAbortException)
        {
            // Normal termination
        }
        catch (Exception e)
        {
            Debug.LogError($"Continuous IP send error: {e}");
        }
    }

    // Modified SendIPAddress to accept device identifier
    private void SendIPAddress(string localIP, string deviceIdentifier)
    {
        try
        {
            using (UdpClient tempClient = new UdpClient())
            {
                IPEndPoint serverEndPoint = new IPEndPoint(
                    IPAddress.Parse(SharedVariables.Instance.serverIP),
                    SharedVariables.Instance.serverPort
                );

                string message = $"{deviceIdentifier}:{localIP}";
                byte[] sendBytes = Encoding.ASCII.GetBytes(message);
                tempClient.Send(sendBytes, sendBytes.Length, serverEndPoint);
                Debug.Log("BetaTest: IP Message Sent - " + message);
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error sending IP: {e}");
        }
    }


    string GetLocalIPAddress()
    {
        var host = Dns.GetHostEntry(Dns.GetHostName());
        foreach (var ip in host.AddressList)
        {
            if (ip.AddressFamily == AddressFamily.InterNetwork && ip.ToString().StartsWith("10.197."))
            {
                return ip.ToString();
            }
        }
        return string.Empty;
    }

    // void SendIPAddress(string localIP)
    // {
    //     try
    //     {
    //         sendClient = new UdpClient();
    //         IPEndPoint serverEndPoint = new IPEndPoint(IPAddress.Parse(SharedVariables.Instance.serverIP), SharedVariables.Instance.serverPort);
    //         string message = $"Magic Leap2:{localIP}";
    //         byte[] sendBytes = Encoding.ASCII.GetBytes(message);
    //         sendClient.Send(sendBytes, sendBytes.Length, serverEndPoint);
    //         sendClient.Close();
    //         Debug.Log("IP Message Sent");
    //     }
    //     catch (System.Exception e)
    //     {
    //         Debug.LogError($"Error sending IP: {e}");
    //     }
    // }

    void ReceiveData()
    {
        receiveClient = new UdpClient(SharedVariables.Instance.receivePort);

        try
        {
            IPEndPoint remoteEP = new IPEndPoint(IPAddress.Any, 0);
            while (isListening)
            {
                byte[] data = receiveClient.Receive(ref remoteEP);

                if (data.Length == sizeof(double)) // Timestamp message
                {
                    // Handle endianness
                    if (!firstTimestampReceived)
                    {
                        firstTimestampReceived = true;
                        Debug.Log("BetaTest: First timestamp received - stopping IP broadcasts");
                        // upload file name should be current time
                        var date = DateTime.Now.ToString("yyyy_MM_dd_HH_mm");
                        SharedVariables.Instance.uploadFileName = $"device_trajectory_logs/MagicLeap2_{date}.csv";
                    }
                    // if (BitConverter.IsLittleEndian)
                    // {
                    //     Array.Reverse(data);
                    // }
                    // Debug.Log("BetaTest: Server Timestamp received: ");

                    double serverTimestamp = BitConverter.ToDouble(data, 0);
                    // Debug.Log("Received Timestamp: " + serverTimestamp);

                    double localTimestamp = Time.timeAsDouble;
                    double difference = serverTimestamp - localTimestamp;
                    // Debug.Log("BetaTest: Difference: " + difference);

                    lock (differencesList)
                    {
                        differencesList.Add(difference);
                    }
                }
                else // Text message
                {
                    string message = Encoding.ASCII.GetString(data);
                    if (message == "Stop Sync")
                    {
                        Debug.Log("BetaTest: StopSync message received");
                        ComputeAverageOffset();
                    }
                    else if (message == "Stop Collection")
                    {
                        Debug.Log("BetaTest: Stop Collection message received");
                        SharedVariables.Instance.quitApp = true;
                    }


                }
            }
        }
        catch (SocketException ex) when (ex.ErrorCode == 10004)
        {
            // Expected exception when closing
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Receive error: {e}");
        }
        finally
        {
            receiveClient.Close();
        }
    }

    void ComputeAverageOffset()
    {
        lock (differencesList)
        {

            Debug.Log("BetaTest: difference list count: " + differencesList.Count);
            if (differencesList.Count > 0)
            {
                SharedVariables.Instance.timestampOffset = (double)differencesList.Average();
                SharedVariables.Instance.timestampOffsetComputed = true;
                Debug.Log($"Average offset calculated: {timestampOffset} ticks");
            }
            else
            {
                Debug.LogWarning("No timestamps received for offset calculation");
                SharedVariables.Instance.timestampOffset = 0;
            }
        }
    }

    void OnDestroy()
    {
        isListening = false;
        stopSending = true;

        if (receiveClient != null)
            receiveClient.Close();

        if (receiveThread != null && receiveThread.IsAlive)
            receiveThread.Join();

        if (sendThread != null && sendThread.IsAlive)
            sendThread.Join();

        if (sendClient != null)
            sendClient.Close();
    }
}